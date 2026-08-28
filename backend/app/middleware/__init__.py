"""
中间件
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import SessionLocal
from app.services.proxy_service import ProxyService


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
        # 检查是否需要认证
        if any(request.url.path.startswith(path) for path in self.EXCLUDE_PATHS):
            return await call_next(request)
        
        # 检查是否是代理请求（排除管理接口）
        if not request.url.path.startswith("/api/v1/proxy/"):
            return await call_next(request)
        
        # 获取API Key
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "缺少Authorization请求头"}
            )
        
        api_key = auth_header.replace("Bearer ", "")
        
        # 验证API Key
        db = SessionLocal()
        try:
            proxy_service = ProxyService(db)
            
            # 验证Key
            key_obj = proxy_service.verify_api_key(api_key)
            if not key_obj:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "无效的API Key"}
                )
            
            # 获取用户
            user = proxy_service.get_user_from_key(key_obj)
            if not user:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "用户已被禁用"}
                )
            
            # 将用户和Key信息存入请求状态
            request.state.user = user
            request.state.api_key = key_obj
            
        finally:
            db.close()
        
        return await call_next(request)
