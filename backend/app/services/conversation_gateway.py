"""Translate the supported conversation APIs through configured channels."""
import json
import logging
import time

import httpx
from fastapi import HTTPException
from fastapi.responses import Response

from app.models.api_key import ApiKey
from app.models.user import User
from app.services.provider_adapters import get_provider_adapter, resolve_upstream_format
from app.services.protocol_conversion import convert_request, convert_response

logger = logging.getLogger(__name__)

_PATHS = {
    "chat": "chat/completions",
    "anthropic": "messages",
    "responses": "responses",
    "gemini": None,
    "custom": None,
}


def _usage(body, source, service, request_data):
    if not isinstance(body, dict) or not isinstance(body.get("usage"), dict):
        raise HTTPException(502, "上游未返回用量，无法结算")
    usage = body["usage"]
    prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
    if source == "anthropic":
        prompt = int(prompt or 0) + int(usage.get("cache_read_input_tokens", 0) or 0) + int(usage.get("cache_creation_input_tokens", 0) or 0)
    prompt, completion = int(prompt or 0), int(completion or 0)
    canonical = {"prompt_tokens": prompt, "completion_tokens": completion,
                 "total_tokens": prompt + completion}
    return service.calculate_tokens({"max_tokens": 0}, {"usage": canonical})


async def proxy_conversation(request, db, source):
    user: User = getattr(request.state, "user", None)
    api_key: ApiKey = getattr(request.state, "api_key", None)
    if not user or not api_key:
        raise HTTPException(401, "无效的API Key")
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(400, "请求体必须是 JSON") from exc
    if not isinstance(body, dict):
        raise HTTPException(400, "请求体必须是 JSON 对象")
    model = body.get("model")
    if not isinstance(model, str) or not model:
        raise HTTPException(422, "缺少 model")

    from app.services.proxy_service import create_proxy_service
    from app.services.quota_reservation_service import estimate_request
    from app.services.rate_limit_service import (
        check_proxy_rate_limit, get_rate_limit_redis_client, release_proxy_concurrency,
    )

    service = create_proxy_service(db)
    access = service.check_model_group_access(api_key, user, model)
    if not access["allowed"]:
        raise HTTPException(403, access["message"])
    if source == "responses":
        # Admission estimates must not require a lossy conversion of native tools/history.
        estimate_data = {
            "messages": [{"role": "user", "content": json.dumps(body, ensure_ascii=False)}],
            "max_tokens": body.get("max_output_tokens", 1024),
        }
    else:
        try:
            chat_request = convert_request(body, source, "chat")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        estimate_data = {**chat_request, "max_tokens": chat_request.get("max_tokens", chat_request.get("max_output_tokens", 1024))}
    estimated = sum(estimate_request(estimate_data))
    redis = get_rate_limit_redis_client()
    limit = check_proxy_rate_limit(redis, api_key, user, model, estimated)
    concurrency_key = limit.get("concurrency_key")
    if not limit["allowed"]:
        from app.services.api_key_freeze_service import record_api_key_error
        record_api_key_error(db, api_key, "rate_limit")
        raise HTTPException(429, limit.get("detail") or "请求过于频繁",
                            headers={"Retry-After": str(max(1, (limit.get("retry_after_ms", 1000) + 999) // 1000))})

    try:
        service.reserve_quota(user, api_key, model, estimate_data)
    except BaseException:
        release_proxy_concurrency(redis, concurrency_key)
        raise

    candidates = service.select_candidates(model, user, api_key)
    if not candidates:
        service.release_reservation()
        release_proxy_concurrency(redis, concurrency_key)
        raise HTTPException(502, "无可用渠道")

    streaming = bool(body.get("stream"))
    start = time.time()
    upstream_response = None
    upstream_client = None
    selected = None
    try:
        for channel, model_channel, key in candidates:
            adapter = get_provider_adapter(channel)
            upstream_format = resolve_upstream_format(channel).value
            if upstream_format not in _PATHS:
                continue
            try:
                if upstream_format in {"gemini", "custom"}:
                    upstream_body = adapter.transform_request(convert_request(body, source, "chat"), model_channel.upstream_model)
                else:
                    upstream_body = convert_request(body, source, upstream_format, model_channel.upstream_model)
            except ValueError:
                continue
            if streaming and upstream_format in {"chat", "custom"}:
                upstream_body["stream_options"] = {**upstream_body.get("stream_options", {}), "include_usage": True}
            headers = adapter.build_headers(channel, key)
            headers["Content-Type"] = "application/json"
            for name in ("anthropic-version", "anthropic-beta"):
                if request.headers.get(name):
                    headers[name] = request.headers[name]
            upstream_client = httpx.Client(timeout=channel.timeout)
            if upstream_format in {"gemini", "custom"}:
                url = adapter.build_url(channel, model_channel.upstream_model)
                if streaming and upstream_format == "gemini":
                    url = url.replace(":generateContent", ":streamGenerateContent") + "?alt=sse"
            else:
                url = adapter.build_protocol_url(channel, _PATHS[upstream_format])
            upstream_request = upstream_client.build_request("POST", url, json=upstream_body, headers=headers)
            try:
                if streaming:
                    upstream_response = upstream_client.send(upstream_request, stream=True)
                else:
                    upstream_response = upstream_client.send(upstream_request)
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError):
                upstream_client.close()
                upstream_client = None
                continue
            selected = (channel, model_channel, adapter, upstream_format)
            if upstream_response.status_code >= 400:
                if upstream_response.status_code in {429, 500, 502, 503, 504}:
                    service.bump_key_failure(channel, key)
                upstream_response.close()
                upstream_client.close()
                upstream_response = upstream_client = None
                continue
            break
        if upstream_response is None or selected is None:
            raise HTTPException(502, "所有上游渠道均请求失败")

        channel, model_channel, adapter, upstream_format = selected
        if streaming:
            from app.services.protocol_stream import ProtocolStream
            from app.api.streaming import QuotaStreamingResponse
            from app.core.database import SessionLocal

            protocol_source = "chat" if upstream_format in {"gemini", "custom"} else upstream_format
            response_stream = ProtocolStream(protocol_source, source, model)
            reservation_id = service.reservation_id
            user_id, key_id, request_id = user.user_id, api_key.key_id, request.state.request_id
            usage_data = service.capture_usage_attribution(key_id)

            def generate():
                completed = False
                terminal_chunks = []
                error = None
                ready = False
                try:
                    with service.reservation_lease():
                        event_name, data_lines = "", []
                        for line in upstream_response.iter_lines():
                            if upstream_format == "gemini" and line.startswith("data:"):
                                converted_lines = adapter.transform_stream_line(line)
                                for converted in converted_lines:
                                    payload = converted[6:] if converted.startswith("data: ") else converted
                                    for chunk in response_stream.feed("", payload):
                                        yield chunk
                                continue
                            if not line:
                                if data_lines:
                                    for chunk in response_stream.feed(event_name, "\n".join(data_lines)):
                                        yield chunk
                                event_name, data_lines = "", []
                            elif line.startswith("event:"):
                                event_name = line[6:].strip()
                            elif line.startswith("data:"):
                                data_lines.append(line[5:].lstrip())
                        if data_lines:
                            for chunk in response_stream.feed(event_name, "\n".join(data_lines)):
                                yield chunk
                        if upstream_format in {"gemini", "custom"} and not response_stream.completed:
                            for chunk in response_stream.feed("", "[DONE]"):
                                yield chunk
                        if response_stream.completed and response_stream.usage:
                            terminal_chunks = response_stream.finish()
                            ready = True
                        else:
                            error = "上游流未正常结束或未返回用量，无法结算"
                        with SessionLocal() as settlement_db:
                            settle = create_proxy_service(settlement_db)
                            settle.reservation_id = reservation_id
                            if ready:
                                tokens = settle.calculate_tokens({"max_tokens": 0}, {"usage": response_stream.usage})
                                settle.record_usage(user_id, key_id, channel.channel_id, model, tokens,
                                    int((time.time() - start) * 1000), 200,
                                    attribution=usage_data, api_type=source,
                                    request_content=body, response_content=response_stream.response)
                                user_row = settlement_db.query(User).filter_by(user_id=user_id).populate_existing().one()
                                key_row = settlement_db.query(ApiKey).filter_by(key_id=key_id).populate_existing().one()
                                import asyncio
                                asyncio.run(settle.deduct_quota(user_row, key_row, tokens))
                                completed = True
                            else:
                                settle.record_usage(user_id, key_id, channel.channel_id, model, {},
                                    int((time.time() - start) * 1000), 502, error,
                                    attribution=usage_data, api_type=source, request_content=body)
                                settlement_db.commit()
                except Exception:
                    completed = False
                    error = "上游流式请求失败"
                    logger.exception("conversation stream failed request_id=%s", request_id)
                finally:
                    upstream_response.close()
                    upstream_client.close()
                if completed:
                    yield from terminal_chunks
                elif error:
                    if source == "anthropic":
                        yield "event: error\ndata: " + json.dumps({"type": "error", "error": {"type": "api_error", "message": error}}, ensure_ascii=False) + "\n\n"
                    elif source == "responses":
                        yield "event: response.failed\ndata: " + json.dumps({"type": "response.failed", "response": {"status": "failed", "error": {"message": error}}}, ensure_ascii=False) + "\n\n"
                    else:
                        yield "data: " + json.dumps({"error": {"message": error, "type": "server_error"}}, ensure_ascii=False) + "\n\n"
            def close_upstream():
                try:
                    upstream_response.close()
                    upstream_client.close()
                finally:
                    release_proxy_concurrency(redis, concurrency_key)

            return QuotaStreamingResponse(generate(), db.get_bind(), reservation_id, on_close=close_upstream)

        try:
            upstream_data = upstream_response.json()
            if upstream_format in {"gemini", "custom"}:
                upstream_data = adapter.transform_response(upstream_data)
                protocol_source = "chat"
            else:
                upstream_data = adapter.transform_protocol_response(upstream_data)
                protocol_source = upstream_format
            result = convert_response(upstream_data, protocol_source, source, model)
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(502, f"上游响应无法转换: {exc}") from exc
        tokens = _usage(upstream_data, protocol_source, service, estimate_data)
        service.record_usage(user.user_id, api_key.key_id, channel.channel_id, model, tokens,
            int((time.time() - start) * 1000), 200, api_type=source,
            request_content=body, response_content=result)
        await service.deduct_quota(user, api_key, tokens)
        return Response(content=json.dumps(result, ensure_ascii=False), media_type="application/json")
    except BaseException:
        try:
            service.release_reservation()
        finally:
            release_proxy_concurrency(redis, concurrency_key)
        raise
    finally:
        if upstream_response is not None and not streaming:
            upstream_response.close()
        if upstream_client is not None and not streaming:
            upstream_client.close()
