"""
WebSocket 端点
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.security import decode_access_token
from app.services.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/notifications")
async def websocket_notifications(websocket: WebSocket, token: str = Query(...)):
    """WebSocket 通知端点"""
    
    # 验证 JWT token
    payload = decode_access_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    # 获取用户ID
    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return
    
    # 连接成功
    await manager.connect(websocket, user_id)
    
    try:
        # 查询未读数（Task 2 中实现，Task 1 用 try/import 兼容处理）
        unread = 0
        try:
            from app.services.notification_service import get_unread_count
            unread = await get_unread_count(user_id)
        except ImportError:
            pass
        
        # 推送连接成功消息
        await websocket.send_json({
            "type": "connected",
            "unread_count": unread
        })
        
        # 心跳循环
        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception:
        manager.disconnect(websocket, user_id)
