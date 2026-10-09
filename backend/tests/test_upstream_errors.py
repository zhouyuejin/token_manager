from app.services.upstream_errors import format_upstream_error


def test_documented_provider_errors_and_unknown_fallback():
    cases = [
        ("minimax", 500, {"error": {"message": "insufficient balance (1008)"}}, "MiniMax：账户余额不足，请检查余额（错误码 1008）"),
        ("minimax", 429, {"base_resp": {"status_code": 2056}}, "MiniMax：套餐用量已达上限，请等待额度重置（错误码 2056）"),
        ("openai", 429, {"error": {"type": "insufficient_quota", "code": "credit_balance_exhausted"}}, "OpenAI：预付费余额已用完（错误码 credit_balance_exhausted）"),
        ("anthropic", 529, {"error": {"type": "overloaded_error", "message": "Overloaded"}}, "Claude：服务暂时繁忙，请稍后重试（错误码 overloaded_error）"),
        ("google", 429, {"error": {"status": "RESOURCE_EXHAUSTED", "code": 429}}, "Gemini：请求或用量已达到限制（错误码 RESOURCE_EXHAUSTED）"),
        ("google", 402, {"error": {"status": "RESOURCE_EXHAUSTED", "code": 402}}, "Gemini：预付费余额已用完（错误码 RESOURCE_EXHAUSTED）"),
        ("deepseek", 402, {"error": {"message": "Payment Required"}}, "DeepSeek：账户余额不足，请检查余额（错误码 402）"),
        ("openai", 400, {"error": {"code": "new_error", "message": "Specific cause"}}, "Specific cause（错误码 new_error）"),
        ("minimax", 500, None, "MiniMax：账户余额不足，请检查余额（错误码 1008）"),
    ]
    for provider, status, payload, expected in cases:
        raw_text = "insufficient balance (1008)" if payload is None else ""
        assert format_upstream_error(provider, status, payload, raw_text) == expected
