"""预扣估算测试直接调用生产逻辑，不复制估算公式。"""
import pytest
from fastapi import HTTPException
from app.services.quota_reservation_service import estimate_request


@pytest.mark.parametrize('messages,output,want', [
    ([{'role': 'user', 'content': 'hi'}], None, (54, 1024)),
    ([{'role': 'user', 'content': '你好'}], 100, (58, 100)),
    ([{'role': 'system', 'content': 'b' * 80}, {'role': 'user', 'content': 'hi'}], 20, (156, 20)),
    ([{'role': 'user', 'content': 'a' * 400}], 50, (452, 50)),
    ([], 10, (32, 10)),
])
def test_request_estimation_includes_input_and_enforces_output(messages, output, want):
    request = {'messages': messages, 'max_tokens': output}
    assert estimate_request(request) == want
    assert request['max_tokens'] == want[1]


@pytest.mark.parametrize('output', [0, -1, True])
def test_invalid_output_rejected(output):
    with pytest.raises(HTTPException) as exc:
        estimate_request({'messages': [], 'max_tokens': output})
    assert exc.value.status_code == 422
