"""
API Key接口
"""
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/")
async def list_api_keys():
    """获取API Key列表"""
    # TODO: 实现
    return {"message": "API Key列表"}


@router.post("/")
async def create_api_key():
    """创建API Key"""
    # TODO: 实现
    return {"message": "创建成功"}


@router.delete("/{key_id}")
async def delete_api_key(key_id: str):
    """删除API Key"""
    # TODO: 实现
    return {"message": "删除成功"}
