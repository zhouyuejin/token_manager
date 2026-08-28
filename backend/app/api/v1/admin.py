"""
管理后台接口
"""
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/users")
async def list_users():
    """用户列表"""
    # TODO: 实现
    return {"message": "用户列表"}


@router.get("/providers")
async def list_providers():
    """供应商列表"""
    # TODO: 实现
    return {"message": "供应商列表"}


@router.get("/providers/{provider_id}/quota")
async def get_provider_quota(provider_id: str):
    """获取供应商配额"""
    # TODO: 实现
    return {
        "provider_id": provider_id,
        "hourly": {"limit": 5000000, "used": 2500000},
        "weekly": {"limit": 20000000, "used": 8000000}
    }
