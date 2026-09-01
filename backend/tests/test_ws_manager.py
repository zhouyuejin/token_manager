"""
WebSocket 连接管理器测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.ws_manager import ConnectionManager


class TestConnectionManager:
    """ConnectionManager 测试类"""
    
    @pytest.fixture
    def manager(self):
        """创建连接管理器实例"""
        return ConnectionManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """创建模拟的 WebSocket"""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.close = AsyncMock()
        return ws
    
    @pytest.mark.asyncio
    async def test_connect(self, manager, mock_websocket):
        """测试连接"""
        user_id = "test_user_123"
        
        await manager.connect(mock_websocket, user_id)
        
        # 验证 accept 被调用
        mock_websocket.accept.assert_called_once()
        # 验证连接被添加到 active_connections
        assert user_id in manager.active_connections
        assert mock_websocket in manager.active_connections[user_id]
    
    @pytest.mark.asyncio
    async def test_disconnect(self, manager, mock_websocket):
        """测试断开连接"""
        user_id = "test_user_456"
        
        # 先连接
        await manager.connect(mock_websocket, user_id)
        assert user_id in manager.active_connections
        
        # 断开
        manager.disconnect(mock_websocket, user_id)
        assert user_id not in manager.active_connections
    
    @pytest.mark.asyncio
    async def test_disconnect_cleans_empty_user(self, manager, mock_websocket):
        """测试断开时清理空用户"""
        user_id = "test_user_789"
        
        # 连接后断开
        await manager.connect(mock_websocket, user_id)
        manager.disconnect(mock_websocket, user_id)
        
        # 验证用户被清理
        assert user_id not in manager.active_connections
    
    @pytest.mark.asyncio
    async def test_send_to_user(self, manager, mock_websocket):
        """测试向用户发送消息"""
        user_id = "test_user_111"
        message = {"type": "test", "content": "hello"}
        
        await manager.connect(mock_websocket, user_id)
        result = await manager.send_to_user(user_id, message)
        
        # 验证发送成功
        assert result is True
        mock_websocket.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_send_to_user_not_exists(self, manager):
        """测试向不存在的用户发送消息"""
        result = await manager.send_to_user("non_existent_user", {"test": "data"})
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_send_to_user_removes_invalid_connections(self, manager):
        """测试发送时移除无效连接"""
        user_id = "test_user_222"
        
        # 创建一个会抛出异常的 WebSocket
        invalid_ws = MagicMock()
        invalid_ws.accept = AsyncMock()
        invalid_ws.send_json = AsyncMock(side_effect=Exception("Connection error"))
        
        # 创建一个正常的 WebSocket
        valid_ws = MagicMock()
        valid_ws.accept = AsyncMock()
        valid_ws.send_json = AsyncMock()
        
        await manager.connect(invalid_ws, user_id)
        await manager.connect(valid_ws, user_id)
        
        # 发送消息，应该清理无效连接
        await manager.send_to_user(user_id, {"test": "data"})
        
        # 验证无效连接被移除
        assert invalid_ws not in manager.active_connections[user_id]
        # 验证有效连接保留
        assert valid_ws in manager.active_connections[user_id]
    
    @pytest.mark.asyncio
    async def test_broadcast(self, manager):
        """测试广播"""
        user1_ws1 = MagicMock()
        user1_ws1.accept = AsyncMock()
        user1_ws1.send_json = AsyncMock()
        user1_ws2 = MagicMock()
        user1_ws2.accept = AsyncMock()
        user1_ws2.send_json = AsyncMock()
        user2_ws = MagicMock()
        user2_ws.accept = AsyncMock()
        user2_ws.send_json = AsyncMock()
        
        await manager.connect(user1_ws1, "user1")
        await manager.connect(user1_ws2, "user1")
        await manager.connect(user2_ws, "user2")
        
        message = {"type": "broadcast", "content": "hello all"}
        await manager.broadcast(message)
        
        # 验证所有连接都收到消息
        user1_ws1.send_json.assert_called_once_with(message)
        user1_ws2.send_json.assert_called_once_with(message)
        user2_ws.send_json.assert_called_once_with(message)
    
    @pytest.mark.asyncio
    async def test_multiple_connections_per_user(self, manager):
        """测试同一用户多个连接（多标签页）"""
        user_id = "test_user_multi"
        
        ws1 = MagicMock()
        ws1.accept = AsyncMock()
        ws2 = MagicMock()
        ws2.accept = AsyncMock()
        
        await manager.connect(ws1, user_id)
        await manager.connect(ws2, user_id)
        
        # 验证两个连接都在同一个用户的集合中
        assert len(manager.active_connections[user_id]) == 2
        assert ws1 in manager.active_connections[user_id]
        assert ws2 in manager.active_connections[user_id]
