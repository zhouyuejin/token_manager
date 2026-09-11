"""
渠道模型 (Channel)

替代原 Provider，支持多 Key 轮询和 Failover
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Integer, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class ChannelType(enum.Enum):
    """渠道类型"""
    openai = "openai"
    anthropic = "anthropic"
    google = "google"
    azure = "azure"
    volcengine = "volcengine"
    moonshot = "moonshot"
    baidu = "baidu"
    custom = "custom"
    # 常用大模型渠道
    minimax = "minimax"
    deepseek = "deepseek"
    zhipu = "zhipu"
    cohere = "cohere"
    mistral = "mistral"
    bedrock = "bedrock"


class UpstreamFormat(enum.Enum):
    """上游 API 格式"""
    auto = "auto"
    chat = "chat"
    anthropic = "anthropic"
    gemini = "gemini"
    responses = "responses"
    custom = "custom"


class AuthType(enum.Enum):
    """认证方式"""
    auto = "auto"
    bearer = "bearer"
    api_key = "api_key"
    azure_api_key = "azure_api_key"
    query_key = "query_key"


class ChannelStatus(enum.Enum):
    """渠道状态"""
    active = "active"
    disabled = "disabled"


class ChannelHealthStatus(enum.Enum):
    """渠道健康状态"""
    healthy = "healthy"
    degraded = "degraded"
    unhealthy = "unhealthy"


class KeyStrategy(enum.Enum):
    """Key 轮询策略"""
    round_robin = "round_robin"
    random = "random"
    sequential = "sequential"


class Channel(Base):
    """渠道表"""
    __tablename__ = "channels"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    channel_id = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False, comment="渠道名称")
    type = Column(Enum(ChannelType), default=ChannelType.openai, nullable=False)
    endpoint = Column(String(255), nullable=True, comment="API端点")
    
    # Key 管理
    api_key = Column(String(255), nullable=False, comment="主 API Key")
    extra_keys = Column(Text, nullable=True, comment="额外 Key 列表 (JSON 数组)")
    key_strategy = Column(String(16), default="round_robin", nullable=False, comment="Key 轮询策略")
    key_health = Column(Text, nullable=True, comment="Key 健康状态 (JSON)")
    
    # 优先级与超时
    priority = Column(Integer, default=0, comment="优先级（数值越大优先级越高）")
    timeout = Column(Integer, default=60, comment="请求超时时间（秒）")
    upstream_format = Column(
        String(32), default="chat", nullable=False,
        comment="上游API格式: chat/anthropic/gemini/responses/auto/custom"
    )
    auth_type = Column(
        String(32), default="auto", nullable=False,
        comment="认证方式: auto/bearer/api_key/azure_api_key/query_key"
    )
    auth_headers = Column(
        Text, nullable=True,
        comment="自定义Header JSON"
    )
    
    # 状态
    status = Column(Enum(ChannelStatus), default=ChannelStatus.active, nullable=False)
    health_status = Column(Enum(ChannelHealthStatus), default=ChannelHealthStatus.healthy, nullable=False, comment="健康状态")
    last_check_at = Column(DateTime, nullable=True, comment="最后检查时间")
    cooldown_until = Column(DateTime, nullable=True, comment="冷却截止时间（路由驱动失败降级后屏蔽）")
    
    # 用量配置
    quota_type = Column(String(20), default="none", comment="配额类型: none/unlimited/limited")
    quota_hourly = Column(BigInteger, default=0, comment="小时配额")
    quota_weekly = Column(BigInteger, default=0, comment="周配额")
    
    # 同步配置
    sync_enabled = Column(Boolean, default=False, comment="是否启用自动同步")
    sync_interval = Column(Integer, default=300, comment="同步间隔（秒）")
    last_sync_at = Column(DateTime, nullable=True, comment="最后同步时间")
    
    # 自定义用量查询配置
    quota_config = Column(Text, nullable=True, comment="自定义用量查询配置JSON")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    model_channels = relationship("ModelChannel", back_populates="channel", cascade="all, delete-orphan")
