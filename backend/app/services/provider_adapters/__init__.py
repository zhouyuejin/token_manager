"""Provider-specific proxy behavior selected from the existing channel format."""
import json
import re
import time
from typing import Any, Dict, List, Optional

from app.models.channel import Channel, ChannelType, AuthType, UpstreamFormat


_DEFAULT_AUTH_BY_TYPE: Dict[ChannelType, AuthType] = {
    ChannelType.openai: AuthType.bearer,
    ChannelType.anthropic: AuthType.api_key,
    ChannelType.azure: AuthType.azure_api_key,
    ChannelType.google: AuthType.bearer,
    ChannelType.volcengine: AuthType.bearer,
    ChannelType.moonshot: AuthType.bearer,
    ChannelType.baidu: AuthType.bearer,
    ChannelType.minimax: AuthType.bearer,
    ChannelType.deepseek: AuthType.bearer,
    ChannelType.zhipu: AuthType.bearer,
    ChannelType.cohere: AuthType.bearer,
    ChannelType.mistral: AuthType.bearer,
    ChannelType.bedrock: AuthType.api_key,
    ChannelType.custom: AuthType.bearer,
}

_DEFAULT_FORMAT_BY_TYPE: Dict[ChannelType, UpstreamFormat] = {
    ChannelType.openai: UpstreamFormat.chat,
    ChannelType.anthropic: UpstreamFormat.anthropic,
    ChannelType.azure: UpstreamFormat.chat,
    ChannelType.google: UpstreamFormat.gemini,
    ChannelType.volcengine: UpstreamFormat.chat,
    ChannelType.moonshot: UpstreamFormat.chat,
    ChannelType.baidu: UpstreamFormat.chat,
    ChannelType.minimax: UpstreamFormat.chat,
    ChannelType.deepseek: UpstreamFormat.chat,
    ChannelType.zhipu: UpstreamFormat.chat,
    ChannelType.cohere: UpstreamFormat.chat,
    ChannelType.mistral: UpstreamFormat.chat,
    ChannelType.bedrock: UpstreamFormat.anthropic,
    ChannelType.custom: UpstreamFormat.chat,
}

_FORMAT_PATH: Dict[UpstreamFormat, str] = {
    UpstreamFormat.chat: "/v1/chat/completions",
    UpstreamFormat.anthropic: "/v1/messages",
    UpstreamFormat.gemini: "/v1beta/models/{model}:generateContent",
    UpstreamFormat.responses: "/v1/responses",
    UpstreamFormat.custom: "/chat/completions",
    UpstreamFormat.auto: "/v1/chat/completions",
}

_AUTH_HEADER_SPEC = {
    AuthType.bearer: ("Authorization", "Bearer {key}"),
    AuthType.api_key: ("x-api-key", "{key}"),
    AuthType.azure_api_key: ("api-key", "{key}"),
    AuthType.query_key: (None, None),
}


def resolve_upstream_format(channel: Channel) -> UpstreamFormat:
    declared = channel.upstream_format
    if declared and declared != UpstreamFormat.auto.value:
        return UpstreamFormat(declared)
    return _DEFAULT_FORMAT_BY_TYPE.get(channel.type, UpstreamFormat.chat)


class ProviderAdapter:
    """Default pass-through behavior; providers override only what differs."""

    def build_headers(self, channel: Channel, api_key: str) -> Dict[str, str]:
        auth_type = channel.auth_type
        if not auth_type or auth_type == AuthType.auto.value:
            auth_type = _DEFAULT_AUTH_BY_TYPE.get(channel.type, AuthType.bearer).value
        header_name, template = _AUTH_HEADER_SPEC.get(AuthType(auth_type), (None, None))
        headers = {header_name: template.format(key=api_key)} if header_name and template else {}
        if channel.auth_headers:
            try:
                extra = json.loads(channel.auth_headers) if isinstance(channel.auth_headers, str) else dict(channel.auth_headers)
            except (json.JSONDecodeError, TypeError):
                extra = {}
            for name, value in extra.items():
                headers.setdefault(name, str(value))
        return headers

    def build_url(self, channel: Channel, model: Optional[str] = None) -> str:
        fmt = resolve_upstream_format(channel)
        base = (channel.endpoint or "").strip().rstrip("/")
        if "/api/coding" in base:
            return f"{base}/v3/chat/completions"
        path = _FORMAT_PATH.get(fmt, "/v1/chat/completions")
        if re.search(r"/v\d+(?:beta)?$", base):
            path = re.sub(r"^/v\d+(?:beta)?/", "/", path)
        if fmt == UpstreamFormat.gemini and "{model}" in path:
            path = path.replace("{model}", model or "default")
        return f"{base}{path}"

    def build_protocol_url(self, channel: Channel, path: str) -> str:
        base = (channel.endpoint or "").strip().rstrip("/")
        if re.search(r"/v\d+(?:beta)?$", base):
            return f"{base}/{path}"
        return f"{base}/v1/{path}"

    def transform_request(self, request_data: Dict[str, Any], upstream_model: str) -> Dict[str, Any]:
        return {**request_data, "model": upstream_model}

    def transform_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        return response_data

    def transform_protocol_request(self, request_data: Dict[str, Any], upstream_model: str) -> Dict[str, Any]:
        return {**request_data, "model": upstream_model}

    def transform_protocol_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        return response_data

    def transform_stream_line(self, line: str) -> List[str]:
        return [line]


class AnthropicAdapter(ProviderAdapter):
    def build_headers(self, channel: Channel, api_key: str) -> Dict[str, str]:
        headers = super().build_headers(channel, api_key)
        headers.setdefault("anthropic-version", "2023-06-01")
        return headers

    def transform_request(self, request_data: Dict[str, Any], upstream_model: str) -> Dict[str, Any]:
        messages = []
        system = []
        for message in request_data.get("messages", []):
            if message.get("role") == "system":
                system.append(message.get("content", ""))
            else:
                messages.append({"role": message.get("role", "user"), "content": message.get("content", "")})
        result = {
            "model": upstream_model,
            "max_tokens": request_data.get("max_tokens") or 1024,
            "messages": messages,
        }
        if system:
            result["system"] = "\n".join(item for item in system if isinstance(item, str))
        for name in ("temperature", "top_p", "stream"):
            if request_data.get(name) is not None:
                result[name] = request_data[name]
        if request_data.get("stop"):
            result["stop_sequences"] = request_data["stop"]
        if request_data.get("tools"):
            result["tools"] = [
                {"name": tool["function"]["name"], "description": tool["function"].get("description", ""),
                 "input_schema": tool["function"].get("parameters", {"type": "object", "properties": {}})}
                for tool in request_data["tools"] if tool.get("type") == "function" and tool.get("function")
            ]
        return result

    def transform_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        message = response_data.get("content", [])
        text = "".join(block.get("text", "") for block in message if block.get("type") == "text")
        input_tokens = int(response_data.get("usage", {}).get("input_tokens", 0) or 0)
        output_tokens = int(response_data.get("usage", {}).get("output_tokens", 0) or 0)
        stop_reason = response_data.get("stop_reason")
        return {
            "id": response_data.get("id", ""),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": response_data.get("model", ""),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text or None},
                         "finish_reason": {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length"}.get(stop_reason, stop_reason)}],
            "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens,
                      "total_tokens": input_tokens + output_tokens},
        }

    def transform_stream_line(self, line: str) -> List[str]:
        if not line.startswith("data: "):
            return []
        try:
            data = json.loads(line[6:])
        except (ValueError, TypeError):
            return []
        event = data.get("type")
        if event == "message_start":
            message = data.get("message", {})
            usage = message.get("usage", {})
            self.input_tokens = int(usage.get("input_tokens", 0) or 0)
            chunk = {"id": message.get("id", ""), "model": message.get("model", ""),
                     "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}
            return ["data: " + json.dumps(chunk)]
        if event == "content_block_delta" and data.get("delta", {}).get("type") == "text_delta":
            chunk = {"choices": [{"index": 0, "delta": {"content": data["delta"].get("text", "")},
                                  "finish_reason": None}]}
            return ["data: " + json.dumps(chunk)]
        if event == "message_delta":
            delta = data.get("delta", {})
            usage = data.get("usage", {})
            output_tokens = int(usage.get("output_tokens", 0) or 0)
            stop_reason = delta.get("stop_reason")
            chunk = {"choices": [{"index": 0, "delta": {},
                                  "finish_reason": {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length"}.get(stop_reason, stop_reason)}],
                     "usage": {"prompt_tokens": getattr(self, "input_tokens", 0),
                               "completion_tokens": output_tokens,
                               "total_tokens": getattr(self, "input_tokens", 0) + output_tokens}}
            return ["data: " + json.dumps(chunk)]
        if event == "message_stop":
            return ["data: [DONE]"]
        return []


class GeminiAdapter(ProviderAdapter):
    def transform_request(self, request_data: Dict[str, Any], upstream_model: str) -> Dict[str, Any]:
        contents = []
        system = []
        for message in request_data.get("messages", []):
            role = message.get("role")
            if role == "system":
                system.append(message.get("content", ""))
            else:
                contents.append({"role": "model" if role == "assistant" else "user",
                                 "parts": [{"text": message.get("content", "")} ]})
        result = {"contents": contents}
        if system:
            result["system_instruction"] = {"parts": [{"text": "\n".join(system)}]}
        config = {}
        for source, target in (("temperature", "temperature"), ("top_p", "topP"),
                               ("max_tokens", "maxOutputTokens"), ("stop", "stopSequences")):
            if request_data.get(source) is not None:
                config[target] = request_data[source]
        if config:
            result["generationConfig"] = config
        return result

    def transform_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        candidates = response_data.get("candidates", [])
        content = candidates[0].get("content", {}) if candidates else {}
        text = "".join(part.get("text", "") for part in content.get("parts", []))
        usage = response_data.get("usageMetadata", {})
        prompt_tokens = int(usage.get("promptTokenCount", 0) or 0)
        completion_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
        finish_reason = candidates[0].get("finishReason") if candidates else None
        return {
            "id": "",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop" if finish_reason == "STOP" else finish_reason}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                      "total_tokens": int(usage.get("totalTokenCount", prompt_tokens + completion_tokens) or 0)},
        }

    def transform_stream_line(self, line: str) -> List[str]:
        if not line.startswith("data: "):
            return []
        try:
            data = json.loads(line[6:])
        except (ValueError, TypeError):
            return []
        candidates = data.get("candidates", [])
        content = candidates[0].get("content", {}) if candidates else {}
        text = "".join(part.get("text", "") for part in content.get("parts", []))
        finish_reason = candidates[0].get("finishReason") if candidates else None
        chunk = {"choices": [{"index": 0, "delta": {"content": text} if text else {},
                              "finish_reason": "stop" if finish_reason == "STOP" else finish_reason}]}
        usage = data.get("usageMetadata")
        if usage:
            prompt_tokens = int(usage.get("promptTokenCount", 0) or 0)
            completion_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
            chunk["usage"] = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                              "total_tokens": int(usage.get("totalTokenCount", prompt_tokens + completion_tokens) or 0)}
        return ["data: " + json.dumps(chunk)]


class ResponsesAdapter(ProviderAdapter):
    def transform_request(self, request_data: Dict[str, Any], upstream_model: str) -> Dict[str, Any]:
        from app.services.protocol_conversion import convert_request
        return convert_request(request_data, "chat", "responses", upstream_model)

    def transform_response(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.protocol_conversion import convert_response
        return convert_response(response_data, "responses", "chat")

    def transform_stream_line(self, line: str) -> List[str]:
        if not line.startswith("data: ") or line[6:].strip() == "[DONE]":
            return []
        from app.services.protocol_stream import ProtocolStream
        if not hasattr(self, "stream"):
            self.stream = ProtocolStream("responses", "chat", "")
        chunks = self.stream.feed("", line[6:])
        if self.stream.completed:
            chunks += self.stream.finish()
        return [chunk.strip() for chunk in chunks]


_ADAPTERS = {
    UpstreamFormat.anthropic: AnthropicAdapter,
    UpstreamFormat.gemini: GeminiAdapter,
    UpstreamFormat.responses: ResponsesAdapter,
}


def get_provider_adapter(channel: Channel) -> ProviderAdapter:
    adapter = _ADAPTERS.get(resolve_upstream_format(channel), ProviderAdapter)
    return adapter() if isinstance(adapter, type) else adapter


def build_auth_headers(channel: Channel, api_key: str) -> Dict[str, str]:
    return get_provider_adapter(channel).build_headers(channel, api_key)


def get_upstream_url(channel: Channel, model: Optional[str] = None) -> str:
    return get_provider_adapter(channel).build_url(channel, model)


def get_upstream_protocol_url(channel: Channel, path: str) -> str:
    return get_provider_adapter(channel).build_protocol_url(channel, path)
