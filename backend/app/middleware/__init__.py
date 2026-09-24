"""
中间件
"""
from fastapi import Request
import secrets
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import SessionLocal
from app.services.proxy_service import ProxyService
from app.services.api_key_freeze_service import record_api_key_error
from app.utils.request import extract_client_ip


class ProxyAuthMiddleware(BaseHTTPMiddleware):
    """代理认证中间件"""
    
    # 不需要认证的路径
    EXCLUDE_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    ]
    
    async def dispatch(self, request: Request, call_next):
        is_proxy_request = request.url.path.startswith(("/api/v1/proxy/", "/api/v1/chats/"))
        if is_proxy_request:
            request.state.request_id = request.headers.get("X-Request-ID") or f"req_{secrets.token_hex(16)}"
        # 检查是否需要认证
        if any(request.url.path.startswith(path) for path in self.EXCLUDE_PATHS):
            return await call_next(request)
        
        # 检查是否是代理请求（排除管理接口）
        if not request.url.path.startswith("/api/v1/proxy/"):
            return await call_next(request)
        
        # 获取API Key
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            response = JSONResponse(
                status_code=401,
                content={"detail": "缺少Authorization请求头"}
            )
            response.headers["X-Request-ID"] = request.state.request_id
            return response
        
        api_key = auth_header.replace("Bearer ", "")
        
        # 验证API Key
        db = SessionLocal()
        try:
            proxy_service = ProxyService(db)
            
            # 验证Key
            key_obj, auth_error = proxy_service.authenticate_api_key(api_key)
            if auth_error or not key_obj:
                if key_obj:
                    record_api_key_error(db, key_obj, "auth")
                response = JSONResponse(
                    status_code=401,
                    content={"detail": auth_error or "无效的API Key"}
                )
                response.headers["X-Request-ID"] = request.state.request_id
                return response
            
            # 获取用户
            user = proxy_service.get_user_from_key(key_obj)
            if not user:
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "用户已被禁用"}
                )
                response.headers["X-Request-ID"] = request.state.request_id
                return response

            if not proxy_service.check_api_key_ip(key_obj, extract_client_ip(request)):
                record_api_key_error(db, key_obj, "ip_mismatch")
                response = JSONResponse(
                    status_code=403,
                    content={"detail": "IP不在API Key白名单内"}
                )
                response.headers["X-Request-ID"] = request.state.request_id
                return response
            
            # 将用户和Key信息存入请求状态
            request.state.user = user
            request.state.api_key = key_obj
            
        finally:
            db.close()
        
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/proxy/"):
            response.headers["X-Request-ID"] = request.state.request_id
        return response
