"""
渠道认证 Header 与上游 URL 构建器

根据 Channel 配置动态选择认证方式和上游端点。
"""
import json
from typing import Dict, Optional
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
    AuthType.bearer:       ("Authorization",   "Bearer {key}"),
    AuthType.api_key:      ("x-api-key",        "{key}"),
    AuthType.azure_api_key: ("api-key",         "{key}"),
    AuthType.query_key:    (None,               None),
}


def _resolve_auth_type(channel: Channel) -> AuthType:
    declared = channel.auth_type
    if declared and declared != AuthType.auto.value:
        return AuthType(declared)
    return _DEFAULT_AUTH_BY_TYPE.get(channel.type, AuthType.bearer)


def _resolve_upstream_format(channel: Channel) -> UpstreamFormat:
    declared = channel.upstream_format
    if declared and declared != UpstreamFormat.auto.value:
        return UpstreamFormat(declared)
    return _DEFAULT_FORMAT_BY_TYPE.get(channel.type, UpstreamFormat.chat)


def build_auth_headers(channel: Channel, api_key: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    auth_type = _resolve_auth_type(channel)
    spec = _AUTH_HEADER_SPEC.get(auth_type, (None, None))
    header_name, template = spec
    if header_name and template:
        headers[header_name] = template.format(key=api_key)

    if channel.auth_headers:
        try:
            extra = json.loads(channel.auth_headers) if isinstance(channel.auth_headers, str) else dict(channel.auth_headers)
        except (json.JSONDecodeError, TypeError):
            extra = {}
        for k, v in extra.items():
            if k in headers:
                continue
            headers[k] = str(v)
    return headers


def _build_url_for_format(endpoint: str, fmt: UpstreamFormat, model: Optional[str] = None) -> str:
    base = endpoint.rstrip("/")
    path_template = _FORMAT_PATH.get(fmt, "/v1/chat/completions")
    if fmt == UpstreamFormat.gemini and "{model}" in path_template:
        path = path_template.replace("{model}", model or "default")
    else:
        path = path_template
    return f"{base}{path}"


def get_upstream_url(channel: Channel, model: Optional[str] = None) -> str:
    fmt = _resolve_upstream_format(channel)
    endpoint = channel.endpoint or ""
    return _build_url_for_format(endpoint, fmt, model)
