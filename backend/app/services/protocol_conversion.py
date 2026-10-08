"""Stateless conversation conversion, with Chat Completions as the common form."""
import copy
import json
import re
import time


_PROTOCOLS = {"chat", "anthropic", "responses"}
_THINK_BLOCK = re.compile(r"<think>[\s\S]*?(?:</think>|$)")
_PARTIAL_THINK_TAG = re.compile(r"<(?:t|th|thi|thin|think)?$")


def _strip_think_text(content):
    if isinstance(content, str):
        return _PARTIAL_THINK_TAG.sub("", _THINK_BLOCK.sub("", content))
    if isinstance(content, list):
        result = copy.deepcopy(content)
        for part in result:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                part["text"] = _strip_think_text(part["text"])
        return result
    return content


def _clean_response(body, protocol):
    """Filter output fields only; tool payloads and measured usage stay intact."""
    result = copy.deepcopy(body)
    if protocol == "chat":
        for choice in result.get("choices", []):
            message = choice.get("message", {})
            for field in ("reasoning_content", "reasoning", "thinking"):
                message.pop(field, None)
            if "content" in message:
                message["content"] = _strip_think_text(message["content"])
    elif protocol == "anthropic":
        result["content"] = [block for block in result.get("content", [])
                             if block.get("type") not in ("thinking", "redacted_thinking")]
        for block in result["content"]:
            if block.get("type") == "text":
                block["text"] = _strip_think_text(block.get("text", ""))
    else:
        result["output"] = [item for item in result.get("output", []) if item.get("type") != "reasoning"]
        for item in result["output"]:
            if item.get("type") == "message":
                item["content"] = _strip_think_text(item.get("content", []))
    return result


def _check(source, target):
    if source not in _PROTOCOLS or target not in _PROTOCOLS:
        raise ValueError("Unsupported conversation protocol")


def _parts(content, source):
    if content is None or isinstance(content, str):
        return content
    result = []
    for block in content:
        kind = block.get("type")
        if kind in {"text", "input_text", "output_text"}:
            result.append({"type": "text", "text": block.get("text", "")})
        elif source == "chat" and kind == "image_url":
            result.append(copy.deepcopy(block))
        elif source == "responses" and kind == "input_image":
            if not block.get("image_url"):
                raise ValueError("Responses file_id images require native protocol")
            image = {"url": block["image_url"]}
            if "detail" in block:
                image["detail"] = block["detail"]
            result.append({"type": "image_url", "image_url": image})
        elif source == "anthropic" and kind == "image":
            image = block.get("source", {})
            if image.get("type") == "base64":
                url = f"data:{image['media_type']};base64,{image['data']}"
            elif image.get("type") == "url":
                url = image["url"]
            else:
                raise ValueError("Unsupported image source")
            result.append({"type": "image_url", "image_url": {"url": url}})
        else:
            raise ValueError(f"Unsupported {source} content type: {kind}")
    return result


def _render_parts(content, target, role="user"):
    if content is None:
        return []
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    result = []
    for block in content:
        if block["type"] == "text":
            kind = "text" if target == "anthropic" else ("output_text" if role == "assistant" else "input_text")
            result.append({"type": kind, "text": block["text"]})
        elif block["type"] == "image_url":
            image = block["image_url"]
            url = image["url"]
            if target == "responses":
                result.append({"type": "input_image", "image_url": url, **({"detail": image["detail"]} if "detail" in image else {})})
            elif url.startswith("data:") and ";base64," in url:
                media, data = url[5:].split(";base64,", 1)
                result.append({"type": "image", "source": {"type": "base64", "media_type": media, "data": data}})
            else:
                result.append({"type": "image", "source": {"type": "url", "url": url}})
        else:
            raise ValueError("Unsupported canonical content")
    return result


def _call(identifier, name, arguments):
    return {"id": identifier, "type": "function", "function": {"name": name, "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False)}}


def _messages(body, source):
    if source == "chat":
        messages = copy.deepcopy(body.get("messages", []))
        for message in messages:
            if message.get("role") not in {"system", "developer", "user", "assistant", "tool"}:
                raise ValueError("Unsupported Chat message role")
            message["content"] = _parts(message.get("content"), source)
            for call in message.get("tool_calls", []):
                if call.get("type") != "function":
                    raise ValueError("Unsupported Chat tool call")
        return messages
    messages = []
    prompt = body.get("system" if source == "anthropic" else "instructions")
    if prompt:
        messages.append({"role": "system", "content": _parts(prompt, source)})
    items = body.get("messages" if source == "anthropic" else "input", [])
    if isinstance(items, str):
        items = [{"role": "user", "content": items}]
    for item in items:
        kind = item.get("type", "message")
        if source == "responses" and kind == "function_call":
            messages.append({"role": "assistant", "content": None, "tool_calls": [_call(item["call_id"], item["name"], item["arguments"])]})
        elif source == "responses" and kind == "function_call_output":
            messages.append({"role": "tool", "tool_call_id": item["call_id"], "content": _parts(item.get("output", ""), source)})
        elif kind == "message":
            role = item.get("role", "user")
            content = item.get("content", "")
            if source != "anthropic" or isinstance(content, str):
                messages.append({"role": role, "content": _parts(content, source)})
                continue
            parts, calls = [], []
            for block in content:
                if block.get("type") == "tool_use":
                    calls.append(_call(block["id"], block["name"], block.get("input", {})))
                elif block.get("type") == "tool_result":
                    if parts or calls:
                        messages.append({"role": role, "content": parts or None, **({"tool_calls": calls} if calls else {})})
                        parts, calls = [], []
                    tool_content = _parts(block.get("content", ""), source)
                    if block.get("is_error"):
                        # Chat/Responses have no is_error field; preserve failure in the output.
                        marker = "Tool execution failed:"
                        tool_content = (marker + "\n" + tool_content if isinstance(tool_content, str)
                                        else [{"type": "text", "text": marker}, *(tool_content or [])])
                    messages.append({"role": "tool", "tool_call_id": block["tool_use_id"], "content": tool_content})
                else:
                    parts.extend(_parts([block], source))
            if parts or calls:
                messages.append({"role": role, "content": parts or None, **({"tool_calls": calls} if calls else {})})
        else:
            raise ValueError(f"Unsupported Responses item type: {kind}")
    return messages


def _tools(tools, source):
    result = []
    for tool in tools:
        if source == "anthropic":
            if tool.get("type") not in {None, "custom"}:
                raise ValueError("Unsupported Anthropic built-in tool")
            function = {"name": tool["name"], "parameters": tool.get("input_schema", {})}
            if "description" in tool:
                function["description"] = tool["description"]
        else:
            if tool.get("type") != "function":
                raise ValueError("Unsupported non-function tool")
            function = copy.deepcopy(tool["function"] if source == "chat" else {k: v for k, v in tool.items() if k != "type"})
        result.append({"type": "function", "function": function})
    return result


def _choice(choice, source, target):
    if source == "anthropic":
        kind = choice.get("type")
        choice = {"auto": "auto", "any": "required", "none": "none"}.get(kind, {"type": "function", "function": {"name": choice.get("name")}} if kind == "tool" else None)
    elif source == "responses" and isinstance(choice, dict):
        if choice.get("type") != "function":
            raise ValueError("Unsupported tool choice")
        choice = {"type": "function", "function": {"name": choice["name"]}}
    if choice is None or (isinstance(choice, dict) and (choice.get("type") != "function" or not choice.get("function", {}).get("name"))):
        raise ValueError("Unsupported tool choice")
    if isinstance(choice, str) and choice not in {"auto", "none", "required"}:
        raise ValueError("Unsupported tool choice")
    if target == "chat":
        return choice
    if target == "responses":
        return {"type": "function", "name": choice["function"]["name"]} if isinstance(choice, dict) else choice
    return {"type": "tool", "name": choice["function"]["name"]} if isinstance(choice, dict) else {"type": {"required": "any", "auto": "auto", "none": "none"}[choice]}


def _render_messages(messages, target):
    items, system = [], []
    for message in messages:
        role = message["role"]
        content = message.get("content")
        if target == "anthropic" and role in {"system", "developer"}:
            system.extend(_render_parts(content, target, role))
            continue
        if role == "tool":
            if target == "responses":
                items.append({"type": "function_call_output", "call_id": message["tool_call_id"], "output": content if isinstance(content, str) else _render_parts(content, target)})
            else:
                items.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": message["tool_call_id"], "content": content if isinstance(content, str) else _render_parts(content, target)}]})
            continue
        parts = _render_parts(content, target, role)
        calls = message.get("tool_calls", [])
        if target == "anthropic":
            for call in calls:
                try:
                    arguments = json.loads(call["function"]["arguments"])
                except (ValueError, TypeError) as exc:
                    raise ValueError("Tool arguments must be JSON for Anthropic") from exc
                parts.append({"type": "tool_use", "id": call["id"], "name": call["function"]["name"], "input": arguments})
            if items and items[-1]["role"] == role:
                items[-1]["content"].extend(parts)
            else:
                items.append({"role": role, "content": parts})
        else:
            if parts:
                items.append({"type": "message", "role": role, "content": parts})
            for call in calls:
                items.append({"type": "function_call", "call_id": call["id"], "name": call["function"]["name"], "arguments": call["function"]["arguments"]})
    return items, system


def convert_request(body, source, target, model=None):
    """Convert stateless requests; native requests retain all opaque fields."""
    _check(source, target)
    if source == target:
        result = copy.deepcopy(body)
        if model is not None:
            result["model"] = model
        return result
    if source == "responses" and body.get("previous_response_id"):
        raise ValueError("previous_response_id requires native Responses history")
    if source == "responses" and body.get("conversation"):
        raise ValueError("conversation requires native Responses history")
    messages = _messages(body, source)
    result = {k: copy.deepcopy(body[k]) for k in ("model", "temperature", "top_p", "stream", "metadata") if k in body}
    if model is not None:
        result["model"] = model
    cap = body.get("max_output_tokens" if source == "responses" else "max_tokens", body.get("max_completion_tokens"))
    if cap is not None or target == "anthropic":
        result["max_output_tokens" if target == "responses" else "max_tokens"] = cap if cap is not None else 1024
    stop = body.get("stop_sequences" if source == "anthropic" else "stop")
    if stop is not None and target != "responses":
        result["stop_sequences" if target == "anthropic" else "stop"] = [stop] if isinstance(stop, str) and target == "anthropic" else stop
    elif stop is not None:
        raise ValueError("Responses does not support stop sequences")
    if target == "chat":
        result["messages"] = messages
    else:
        items, system = _render_messages(messages, target)
        result["messages" if target == "anthropic" else "input"] = items
        if system:
            result["system"] = system
    if "tools" in body:
        tools = _tools(body["tools"], source)
        if target == "chat":
            result["tools"] = tools
        elif target == "responses":
            result["tools"] = [{"type": "function", **tool["function"]} for tool in tools]
        else:
            result["tools"] = [{"name": tool["function"]["name"], "input_schema": tool["function"].get("parameters", {}), **({"description": tool["function"]["description"]} if "description" in tool["function"] else {})} for tool in tools]
    if "tool_choice" in body:
        result["tool_choice"] = _choice(body["tool_choice"], source, target)
    parallel = body.get("parallel_tool_calls")
    if source == "anthropic" and isinstance(body.get("tool_choice"), dict) and "disable_parallel_tool_use" in body["tool_choice"]:
        parallel = not body["tool_choice"]["disable_parallel_tool_use"]
    if parallel is not None:
        if target == "anthropic":
            result.setdefault("tool_choice", {"type": "auto"})["disable_parallel_tool_use"] = not parallel
        else:
            result["parallel_tool_calls"] = parallel
    return result


def _usage(usage, source):
    if source == "chat":
        return copy.deepcopy(usage)
    incoming = int(usage.get("input_tokens", 0) or 0)
    outgoing = int(usage.get("output_tokens", 0) or 0)
    details = copy.deepcopy(usage.get("input_tokens_details", {}))
    if source == "anthropic":
        cached = int(usage.get("cache_read_input_tokens", 0) or 0)
        created = int(usage.get("cache_creation_input_tokens", 0) or 0)
        incoming += cached + created
        if cached or "cache_read_input_tokens" in usage:
            details["cached_tokens"] = cached
        if created or "cache_creation_input_tokens" in usage:
            details["cache_creation_tokens"] = created
    result = {"prompt_tokens": incoming, "completion_tokens": outgoing, "total_tokens": incoming + outgoing}
    if details:
        result["prompt_tokens_details"] = details
    if usage.get("output_tokens_details"):
        result["completion_tokens_details"] = copy.deepcopy(usage["output_tokens_details"])
    return result


def _render_usage(usage, target):
    if target == "chat":
        return usage
    incoming = usage.get("prompt_tokens", 0)
    outgoing = usage.get("completion_tokens", 0)
    details = usage.get("prompt_tokens_details", {})
    if target == "anthropic":
        result = {"input_tokens": incoming - details.get("cached_tokens", 0) - details.get("cache_creation_tokens", 0), "output_tokens": outgoing}
        for source, dest in (("cached_tokens", "cache_read_input_tokens"), ("cache_creation_tokens", "cache_creation_input_tokens")):
            if source in details:
                result[dest] = details[source]
        return result
    result = {"input_tokens": incoming, "output_tokens": outgoing, "total_tokens": incoming + outgoing}
    if details:
        result["input_tokens_details"] = details
    if usage.get("completion_tokens_details"):
        result["output_tokens_details"] = usage["completion_tokens_details"]
    return result


def convert_response(body, source, target, model=None):
    """Convert completed responses, preserving measured usage and tool call IDs."""
    _check(source, target)
    body = _clean_response(body, source)
    if source == target:
        result = body
        if model is not None:
            result["model"] = model
        return result
    if source == "chat":
        choices = body.get("choices", [])
        if len(choices) != 1:
            raise ValueError("Cross-protocol conversion requires one response choice")
        message = _messages({"messages": [choices[0]["message"]]}, "chat")[0]
        reason = choices[0].get("finish_reason")
    elif source == "anthropic":
        messages = _messages({"messages": [{"role": "assistant", "content": body.get("content", [])}]}, source)
        if len(messages) > 1:
            raise ValueError("Invalid Anthropic assistant response")
        message = messages[0] if messages else {"role": "assistant", "content": None}
        reason = {"end_turn": "stop", "stop_sequence": "stop", "max_tokens": "length", "tool_use": "tool_calls", "refusal": "content_filter"}.get(body.get("stop_reason"))
        if reason is None:
            raise ValueError("Unsupported Anthropic stop reason")
    else:
        if body.get("error") or body.get("status") in {"failed", "cancelled", "queued", "in_progress"}:
            raise ValueError("Responses response is not successfully completed")
        messages = _messages({"input": body.get("output", [])}, source)
        parts, calls = [], []
        for item in messages:
            if item["role"] != "assistant":
                raise ValueError("Unexpected Responses output role")
            content = item.get("content")
            if isinstance(content, str):
                parts.append({"type": "text", "text": content})
            elif content:
                parts.extend(content)
            calls.extend(item.get("tool_calls", []))
        message = {"role": "assistant", "content": parts or None}
        if calls:
            message["tool_calls"] = calls
        reason = "tool_calls" if calls else "stop"
        if body.get("status") == "incomplete":
            incomplete = (body.get("incomplete_details") or {}).get("reason")
            if incomplete not in {"max_output_tokens", "content_filter"}:
                raise ValueError("Unsupported Responses incomplete reason")
            reason = "length" if incomplete == "max_output_tokens" else "content_filter"
    content = message.get("content")
    if isinstance(content, list) and all(block["type"] == "text" for block in content):
        message["content"] = "".join(block["text"] for block in content)
    usage = _usage(body["usage"], source) if body.get("usage") is not None else None
    identifier = body.get("id", "")
    chosen_model = model if model is not None else body.get("model", "")
    created = body.get("created", body.get("created_at", int(time.time())))
    if target == "chat":
        result = {"id": identifier, "object": "chat.completion", "created": created, "model": chosen_model, "choices": [{"index": 0, "message": message, "finish_reason": reason}]}
    elif target == "anthropic":
        if reason not in {"stop", "length", "tool_calls", "content_filter"}:
            raise ValueError("Unsupported Chat finish reason")
        items, _ = _render_messages([message], target)
        result = {"id": identifier, "type": "message", "role": "assistant", "model": chosen_model, "content": items[0]["content"] if items else [], "stop_reason": {"stop": "end_turn", "length": "max_tokens", "tool_calls": "tool_use", "content_filter": "refusal"}[reason], "stop_sequence": None}
    else:
        if reason not in {"stop", "length", "tool_calls", "content_filter"}:
            raise ValueError("Unsupported Chat finish reason")
        output, _ = _render_messages([message], target)
        for index, item in enumerate(output):
            item["id"] = f"{identifier}_{index}"
            item["status"] = "completed"
            if item["type"] == "message":
                for block in item["content"]:
                    if block["type"] == "output_text":
                        block["annotations"] = []
        incomplete = reason in {"length", "content_filter"}
        result = {"id": identifier, "object": "response", "created_at": created, "model": chosen_model, "status": "incomplete" if incomplete else "completed", "output": output, "error": None, "incomplete_details": {"reason": "max_output_tokens" if reason == "length" else "content_filter"} if incomplete else None}
    if usage is not None:
        result["usage"] = _render_usage(usage, target)
    return result
