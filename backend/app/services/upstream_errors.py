"""Translate documented upstream errors for user-facing proxy responses."""
import json
import re


# Sources: MiniMax https://platform.minimax.io/docs/api-reference/errorcode
# OpenAI https://developers.openai.com/api/docs/guides/error-codes
# Claude https://platform.claude.com/docs/en/api/errors
# Gemini https://ai.google.dev/gemini-api/docs/generate-content/api-errors
# DeepSeek https://api-docs.deepseek.com/quick_start/error_codes/
_CODES = {
    "minimax": {"1002": "请求过于频繁", "1008": "账户余额不足，请检查余额", "2049": "密钥无效", "2056": "套餐用量已达上限，请等待额度重置"},
    "openai": {"credit_balance_exhausted": "预付费余额已用完", "organization_spend_limit_exceeded": "组织支出上限已达到", "project_spend_limit_exceeded": "项目支出上限已达到", "organization_usage_limit_exceeded": "组织用量上限已达到", "server_is_overloaded": "模型暂时繁忙，请稍后重试", "rate_limit_error": "请求过于频繁，请稍后重试"},
    "anthropic": {"authentication_error": "密钥认证失败", "billing_error": "账单或支付信息异常", "rate_limit_error": "请求或用量已达到限制", "overloaded_error": "服务暂时繁忙，请稍后重试"},
    "google": {"INVALID_ARGUMENT": "请求参数无效", "PERMISSION_DENIED": "密钥没有相应权限", "UNAVAILABLE": "服务暂时不可用，请稍后重试", "DEADLINE_EXCEEDED": "请求处理超时"},
}
_NAMES = {"minimax": "MiniMax", "openai": "OpenAI", "anthropic": "Claude", "google": "Gemini", "deepseek": "DeepSeek"}


def format_upstream_error(provider, status_code, payload=None, raw_text=""):
    """Return a Chinese explanation when the provider and error code are known."""
    provider = getattr(provider, "value", provider)
    if payload is None and raw_text:
        try:
            payload = json.loads(raw_text)
        except ValueError:
            pass
    data = payload if isinstance(payload, dict) else {}
    error = data.get("error", data)
    error = error if isinstance(error, dict) else {"message": error}
    base_resp = data.get("base_resp")
    message = next((value for value in (error.get("message"), data.get("message"), data.get("detail"),
                                        base_resp.get("status_msg") if isinstance(base_resp, dict) else None,
                                        raw_text[:300]) if isinstance(value, str) and value), "")
    code = error.get("code") or (base_resp.get("status_code") if isinstance(base_resp, dict) else None)
    code = str(code) if code is not None else ""
    if provider == "minimax" and not code:
        match = re.search(r"\((1002|1008|2049|2056)\)", message)
        code = match.group(1) if match else ""
    if not code and provider in _CODES:
        code = next((item for item in _CODES[provider] if re.search(rf"(?<![\w]){re.escape(item)}(?![\w])", message)), "")
    key = code if code in _CODES.get(provider, {}) else str(error.get("type") or error.get("status") or "")
    if provider == "google" and not key and "RESOURCE_EXHAUSTED" in message:
        key = "RESOURCE_EXHAUSTED"
    explanation = _CODES.get(provider, {}).get(key)
    if provider == "google" and key == "RESOURCE_EXHAUSTED":
        explanation = "预付费余额已用完" if status_code == 402 else "请求或用量已达到限制" if status_code == 429 else None
    if provider == "deepseek":
        explanation = {401: "密钥认证失败", 402: "账户余额不足，请检查余额", 429: "请求过于频繁", 503: "服务暂时繁忙，请稍后重试"}.get(status_code)
        key = str(status_code) if explanation else ""
    if explanation:
        return f"{_NAMES[provider]}：{explanation}（错误码 {key}）"
    original = message or (raw_text[:300] if raw_text else "") or f"HTTP {status_code}"
    return f"{original}（错误码 {code}）" if code and code not in original else original


def format_upstream_response_error(provider, response):
    return format_upstream_error(provider, response.status_code, raw_text=response.text)
