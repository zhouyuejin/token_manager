"""
API路由
"""
from fastapi import APIRouter

from app.api.v1 import auth, users, api_keys, proxy, stats, admin

api_router = APIRouter()

# 认证
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])

# 用户
api_router.include_router(users.router, prefix="/users", tags=["用户"])

# API Key
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Key"])

# 代理
api_router.include_router(proxy.router, prefix="/proxy", tags=["代理"])

# 统计
api_router.include_router(stats.router, prefix="/stats", tags=["用量统计"])

# 管理后台
api_router.include_router(admin.router, prefix="/admin", tags=["管理后台"])
