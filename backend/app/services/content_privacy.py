"""Small, bounded redaction helpers for persisted logs."""
import re


_SENSITIVE_FIELD = re.compile(
    r'(?i)(["\']?(?:api[_ -]?key|access[_ -]?token|refresh[_ -]?token|authorization|password|secret|id[_ -]?(?:card|number)|身份证号?)["\']?\s*[:=]\s*)(["\']?)([^"\'\s,}\]]+)(["\']?)'
)
_BEARER = re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+')
_PROVIDER_KEY = re.compile(r'\b(?:sk|rk|pk|tmk)[-_][A-Za-z0-9_-]{6,}\b|\bAIza[A-Za-z0-9_-]{20,}\b')
_ID_NUMBER = re.compile(r'(?<!\d)(?:\d{17}[\dXx]|\d{15})(?!\d)')
_PHONE = re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)')
_EMAIL = re.compile(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', re.IGNORECASE)
_CONTENT_KEYS = {
    "messages", "contents", "content", "parts", "text", "input_text", "output_text",
    "prompt", "input", "output", "choices", "message", "delta",
}


def redact_sensitive_text(value: str, limit: int = None) -> str:
    if not value:
        return value
    value = _BEARER.sub("Bearer [REDACTED]", value)
    value = _SENSITIVE_FIELD.sub(r'\1\2[REDACTED]\4', value)
    value = _PROVIDER_KEY.sub("[REDACTED_API_KEY]", value)
    value = _ID_NUMBER.sub("[REDACTED_ID]", value)
    value = _PHONE.sub("[REDACTED_PHONE]", value)
    value = _EMAIL.sub("[REDACTED_EMAIL]", value)
    return value[:limit] if limit is not None else value


def content_summary(payload, limit: int = 2000):
    """Extract only text-bearing fields, cap traversal and redact before persistence."""
    if payload is None:
        return None
    parts = []
    remaining = limit + 256
    visited = 0

    def collect(value, depth=0):
        nonlocal remaining, visited
        if remaining <= 0 or depth > 6 or visited >= 200:
            return
        visited += 1
        if isinstance(value, str):
            chunk = value[:remaining]
            parts.append(chunk)
            remaining -= len(chunk)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item, depth + 1)
                if remaining <= 0 or visited >= 200:
                    break
        elif isinstance(value, dict):
            for key, item in value.items():
                if key in _CONTENT_KEYS and depth < 6:
                    collect(item, depth + 1)
                else:
                    visited += 1
                if remaining <= 0 or visited >= 200:
                    break

    collect(payload)
    summary = "\n".join(parts).strip()
    return redact_sensitive_text(summary)[:limit] if summary else None
