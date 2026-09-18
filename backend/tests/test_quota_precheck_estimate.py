"""预扣估算测试直接调用生产逻辑，不复制估算公式。"""
import pytest
from fastapi import HTTPException
from app.services.quota_reservation_service import estimate_request


@pytest.mark.parametrize('messages,output,want', [
    ([{'role': 'user', 'content': 'hi'}], None, (278, 1024)),
    ([{'role': 'user', 'content': '你好'}], 100, (282, 100)),
    ([{'role': 'system', 'content': 'b' * 80}, {'role': 'user', 'content': 'hi'}], 20, (380, 20)),
    ([{'role': 'user', 'content': 'a' * 400}], 50, (676, 50)),
    ([], 10, (256, 10)),
])
def test_request_estimation_includes_input_and_enforces_output(messages, output, want):
    request = {'messages': messages, 'max_tokens': output}
    assert estimate_request(request) == want
    # 估算函数不应污染入参:配额预扣使用的默认上限(1024)只用于本地估算,
    # 不应被回写到 request_data,否则下游发给上游时会变成隐式 max_tokens 上限,导致长回答被截断。
    assert request.get('max_tokens') == output


@pytest.mark.parametrize('output', [0, -1, True])
def test_invalid_output_rejected(output):
    with pytest.raises(HTTPException) as exc:
        estimate_request({'messages': [], 'max_tokens': output})
    assert exc.value.status_code == 422
