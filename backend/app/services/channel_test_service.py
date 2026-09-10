"""
渠道连接测试服务

通过探测 endpoint + API key 的方式验证渠道连通性，不修改任何持久化数据。
"""
import time
import httpx
from typing import Dict, Any, List, Optional


# Anthropic 使用专属 header
ANTHROPIC_TYPES = {"anthropic"}


class ChannelTestService:
    """渠道连通性测试服务"""

    def _build_headers(self, type_: str, api_key: str) -> Dict[str, str]:
        if type_ in ANTHROPIC_TYPES:
            return {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _build_probe_urls(self, endpoint: str, type_: str) -> List[str]:
        """生成候选探测 URL，覆盖 endpoint 是否带 /v1 的两种情况。"""
        base = endpoint.rstrip("/")
        if type_ in ANTHROPIC_TYPES:
            return [f"{base}/v1/models"]
        # OpenAI 兼容：endpoint 已含 /v1 时优先 {base}/models，否则优先 /v1/models
        if base.endswith("/v1"):
            return [f"{base}/models", f"{base}/v1/models"]
        return [f"{base}/v1/models", f"{base}/models"]

    async def test_connection(
        self,
        type_: str,
        endpoint: str,
        api_key: str,
        timeout: int = 30,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> Dict[str, Any]:
        """
        测试渠道连通性。

        Args:
            transport: 可选的 httpx 传输层，用于注入 mock 进行测试。

        Returns:
            {
                "success": bool,
                "status_code": int | None,
                "latency_ms": int,
                "message": str,
                "url": str | None,
            }
        """
        if not endpoint:
            return {"success": False, "latency_ms": 0, "message": "API 端点不能为空"}
        if not api_key:
            return {"success": False, "latency_ms": 0, "message": "API Key 不能为空"}

        headers = self._build_headers(type_, api_key)
        candidates = self._build_probe_urls(endpoint, type_)
        timeout_s = min(max(int(timeout or 30), 5), 120)

        start = time.time()
        client_kwargs: Dict[str, Any] = {"timeout": timeout_s, "follow_redirects": True}
        if transport is not None:
            client_kwargs["transport"] = transport
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                last_status: Optional[int] = None
                for url in candidates:
                    try:
                        response = await client.get(url, headers=headers)
                    except httpx.ConnectError as e:
                        return {
                            "success": False,
                            "latency_ms": int((time.time() - start) * 1000),
                            "message": f"无法连接到地址 ({type(e).__name__})",
                        }
                    except httpx.TimeoutException:
                        return {
                            "success": False,
                            "latency_ms": int((time.time() - start) * 1000),
                            "message": f"连接超时 (>{timeout_s}s)",
                        }
                    except httpx.RequestError as e:
                        return {
                            "success": False,
                            "latency_ms": int((time.time() - start) * 1000),
                            "message": f"请求失败: {type(e).__name__}",
                        }

                    last_status = response.status_code
                    if response.status_code == 200:
                        return {
                            "success": True,
                            "status_code": 200,
                            "latency_ms": int((time.time() - start) * 1000),
                            "message": "连接成功",
                            "url": url,
                        }
                    if response.status_code in (401, 403):
                        return {
                            "success": False,
                            "status_code": response.status_code,
                            "latency_ms": int((time.time() - start) * 1000),
                            "message": f"API Key 无效或权限不足 (HTTP {response.status_code})",
                            "url": url,
                        }
                    # 路径不对时继续尝试下一个候选
                    if response.status_code == 404:
                        continue
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "latency_ms": int((time.time() - start) * 1000),
                        "message": f"API 响应错误 (HTTP {response.status_code})",
                        "url": url,
                    }
                return {
                    "success": False,
                    "status_code": last_status,
                    "latency_ms": int((time.time() - start) * 1000),
                    "message": f"路径不存在 (HTTP 404): 已尝试 {len(candidates)} 个路径",
                }
        except Exception as e:
            return {
                "success": False,
                "latency_ms": int((time.time() - start) * 1000),
                "message": f"测试异常: {type(e).__name__}: {str(e)[:200]}",
            }
