"""
用户接口
"""
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/me")
async def get_user_info():
    """获取当前用户信息"""
    # TODO: 实现
    return {"message": "用户信息"}
