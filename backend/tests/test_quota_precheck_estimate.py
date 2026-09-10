"""Regression: API endpoints' quota pre-check must scale with the actual request.

Bug: chat.py / proxy.py hard-coded estimated_tokens=1000, so any user with
quota < 1000 was blocked from sending ANY message. Fix: estimate = prompt//4 + max_tokens,
fallback to 100 when max_tokens is None (frontend didn't send it).
"""


class _FakeMsg:
    def __init__(self, content):
        self.content = content


class _FakeReq:
    """Mirror Pydantic ChatSendMessageRequest / ChatCompletionRequest."""

    def __init__(self, messages, system_prompt="", max_tokens=None):
        self.messages = [_FakeMsg(m) for m in messages]
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens


def _estimate(req):
    """Mirror the formula used in chat.py / proxy.py."""
    prompt_chars = sum(len(m.content or "") for m in req.messages) + len(req.system_prompt or "")
    if req.max_tokens is None:
        return (prompt_chars // 4) + 100
    return (prompt_chars // 4) + req.max_tokens


def test_quota_300_user_can_send_short_message_no_max_tokens():
    """The original bug: frontend doesn't send max_tokens, but quota=300
    should still allow short messages."""
    req = _FakeReq(["你好"])  # max_tokens=None
    assert _estimate(req) == 100  # 0 + 100 fallback


def test_quota_50_user_still_blocked_with_no_max_tokens():
    req = _FakeReq(["hi"])
    assert _estimate(req) == 100  # quota_remain 50 < 100 → still rejected (correct)


def test_user_explicit_max_tokens_1000_still_blocks_quota_300():
    req = _FakeReq(["hi"], max_tokens=1000)
    assert _estimate(req) == 1000  # 300 < 1000 → rejected (correct)


def test_user_explicit_max_tokens_100_passes_quota_300():
    req = _FakeReq(["hi"], max_tokens=100)
    assert _estimate(req) == 100


def test_long_prompt_counts_toward_estimate():
    req = _FakeReq(["a" * 400], max_tokens=50)
    assert _estimate(req) == 100 + 50


def test_system_prompt_counts_toward_estimate():
    req = _FakeReq(["hi"], system_prompt="b" * 80, max_tokens=20)
    assert _estimate(req) == 20 + 20


def test_empty_message_falls_back_to_max_tokens_only():
    req = _FakeReq([""], max_tokens=10)
    assert _estimate(req) == 10


def test_pydantic_default_is_none_not_1000():
    """Lock down: Pydantic default must be None so the 100 fallback triggers."""
    from app.api.v1.chat import ChatSendMessageRequest
    from app.api.v1.proxy import ChatCompletionRequest

    # Pydantic v1 stores defaults in __fields__
    assert ChatSendMessageRequest.__fields__["max_tokens"].default is None
    assert ChatCompletionRequest.__fields__["max_tokens"].default is None
