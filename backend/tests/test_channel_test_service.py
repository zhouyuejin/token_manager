"""
ChannelTestService 单元测试，使用 httpx.MockTransport 避免真实网络调用。
"""
import pytest
import httpx

from app.services.channel_test_service import ChannelTestService


def _handler(status: int = 200, body: dict = None):
    """返回 200 的通用 handler"""
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json=body or {"data": []})
    return handle


@pytest.mark.asyncio
async def test_success_openai():
    transport = httpx.MockTransport(_handler(200))
    result = await ChannelTestService().test_connection(
        type_="openai", endpoint="https://api.example.com",
        api_key="sk-test", timeout=10, transport=transport,
    )
    assert result["success"] is True
    assert result["status_code"] == 200
    assert result["message"] == "连接成功"


@pytest.mark.asyncio
async def test_unauthorized_returns_key_error():
    transport = httpx.MockTransport(_handler(401))
    result = await ChannelTestService().test_connection(
        type_="openai", endpoint="https://api.example.com",
        api_key="sk-bad", timeout=10, transport=transport,
    )
    assert result["success"] is False
    assert result["status_code"] == 401
    assert "API Key" in result["message"]


@pytest.mark.asyncio
async def test_404_falls_back_to_alternate_path():
    """endpoint 带 /v1 时应优先尝试 {base}/models，再回退到 /v1/models。"""
    def handle(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://api.example.com/v1/v1/models":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)
    transport = httpx.MockTransport(handle)
    result = await ChannelTestService().test_connection(
        type_="openai", endpoint="https://api.example.com/v1",
        api_key="sk-test", timeout=10, transport=transport,
    )
    assert result["success"] is True
    assert result["url"] == "https://api.example.com/v1/v1/models"


@pytest.mark.asyncio
async def test_connect_error_returns_network_message():
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns failure", request=request)
    transport = httpx.MockTransport(handle)
    result = await ChannelTestService().test_connection(
        type_="openai", endpoint="https://nonexistent.example",
        api_key="sk-test", timeout=10, transport=transport,
    )
    assert result["success"] is False
    assert "地址" in result["message"]


@pytest.mark.asyncio
async def test_anthropic_uses_x_api_key():
    """anthropic 类型应使用 x-api-key header。"""
    seen = {}
    def handle(request: httpx.Request) -> httpx.Response:
        seen.update({k.lower(): v for k, v in request.headers.items()})
        return httpx.Response(200, json={"data": []})
    transport = httpx.MockTransport(handle)
    result = await ChannelTestService().test_connection(
        type_="anthropic", endpoint="https://api.anthropic.com",
        api_key="sk-ant-test", timeout=10, transport=transport,
    )
    assert result["success"] is True
    assert seen.get("x-api-key") == "sk-ant-test"
    assert "authorization" not in seen


@pytest.mark.asyncio
async def test_empty_endpoint_rejected():
    result = await ChannelTestService().test_connection(
        type_="openai", endpoint="", api_key="sk-test", timeout=10,
    )
    assert result["success"] is False
    assert result["message"]


@pytest.mark.asyncio
async def test_empty_api_key_rejected():
    result = await ChannelTestService().test_connection(
        type_="openai", endpoint="https://api.example.com", api_key="", timeout=10,
    )
    assert result["success"] is False
    assert result["message"]


@pytest.mark.asyncio
async def test_all_paths_404_returns_path_not_found():
    transport = httpx.MockTransport(_handler(404))
    result = await ChannelTestService().test_connection(
        type_="openai", endpoint="https://api.example.com",
        api_key="sk-test", timeout=10, transport=transport,
    )
    assert result["success"] is False
    assert result["status_code"] == 404
    assert "路径" in result["message"]


@pytest.mark.asyncio
async def test_other_4xx_returns_error():
    transport = httpx.MockTransport(_handler(418))
    result = await ChannelTestService().test_connection(
        type_="openai", endpoint="https://api.example.com",
        api_key="sk-test", timeout=10, transport=transport,
    )
    assert result["success"] is False
    assert result["status_code"] == 418
    assert "HTTP 418" in result["message"]
