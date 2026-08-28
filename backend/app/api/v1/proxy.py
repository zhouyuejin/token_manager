"""
代理接口 - 核心中转功能
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    stream: Optional[bool] = False


@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionRequest, req: Request):
    """
    大模型API中转接口
    兼容OpenAI格式
    """
    # TODO: 实现
    # 1. 验证API Key
    # 2. 检查额度
    # 3. 路由到对应供应商
    # 4. 转发请求
    # 5. 记录用量
    
    return {
        "id": "chatcmpl-xxx",
        "object": "chat.completion",
        "created": 1699000000,
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "你好，这是中转平台的响应"
            },
            "finish_reason": "stop"
        }]
    }


@router.get("/models")
async def list_models():
    """获取模型列表"""
    # TODO: 实现
    return {
        "object": "list",
        "data": [
            {"id": "gpt-4", "object": "model"},
            {"id": "gpt-3.5-turbo", "object": "model"}
        ]
    }


@router.get("/balance")
async def get_balance():
    """获取余额"""
    # TODO: 实现
    return {
        "balance": 750000,
        "daily_used": 25000,
        "daily_limit": 100000
    }
