"""
WebSocket 连接管理器
"""
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # user_id -> 所有活跃 WebSocket 连接（支持多标签页）
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str) -> None:
        """接受连接并注册"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
    
    def disconnect(self, websocket: WebSocket, user_id: str) -> None:
        """注销连接，自动清理空用户"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            # 清理空用户
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
    
    async def send_to_user(self, user_id: str, message: dict) -> bool:
        """向用户所有连接推送，异常连接自动清理"""
        if user_id not in self.active_connections:
            return False
        
        disconnected = set()
        sent_count = 0
        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message)
                sent_count += 1
            except Exception as e:
                disconnected.add(websocket)
        
        # 清理异常连接
        for ws in disconnected:
            self.disconnect(ws, user_id)
        
        return True
    
    async def broadcast(self, message: dict) -> None:
        """广播给所有在线用户"""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)


# 全局连接管理器实例
manager = ConnectionManager()
