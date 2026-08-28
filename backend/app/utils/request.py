"""
请求工具函数
"""
from typing import Optional

from fastapi import Request


def extract_client_ip(request: Request) -> Optional[str]:
    """
    从请求中提取客户端真实IP。
    优先级: X-Forwarded-For 第一段 > X-Real-IP > request.client.host
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # 取第一段（最原始的客户端IP）
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client:
        return request.client.host
    return None


def extract_user_agent(request: Request) -> Optional[str]:
    """
    从请求头中提取 User-Agent，最多 500 字符。
    """
    ua = request.headers.get("user-agent")
    if ua and len(ua) > 500:
        return ua[:500]
    return ua
