"""
供应商模型

Task 5: 删除 model_groups 关系。
API Key 不再保留独立分组权限，统一由用户分组决定（§2.15）。
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Integer, Text, Boolean, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class ProviderType(enum.Enum):
    """供应商类型"""
    openai = "openai"
    anthropic = "anthropic"
    google = "google"
    azure = "azure"
    volcengine = "volcengine"
    moonshot = "moonshot"
    baidu = "baidu"
    custom = "custom"
    # 常用大模型供应商
    minimax = "minimax"
    deepseek = "deepseek"
    zhipu = "zhipu"
    cohere = "cohere"
    mistral = "mistral"
    bedrock = "bedrock"


class ProviderStatus(enum.Enum):
    """供应商状态"""
    active = "active"
    disabled = "disabled"


class ProviderHealthStatus(enum.Enum):
    """供应商健康状态"""
    healthy = "healthy"
    degraded = "degraded"
    unhealthy = "unhealthy"


class Provider(Base):
    """供应商表"""
    __tablename__ = "providers"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider_id = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False, comment="供应商名称")
    type = Column(Enum(ProviderType), default=ProviderType.openai, nullable=False)
    endpoint = Column(String(255), nullable=True, comment="API端点")
    api_key = Column(String(255), nullable=False, comment="API Key")
    priority = Column(Integer, default=0, comment="优先级（数值越大优先级越高）")
    timeout = Column(Integer, default=60, comment="请求超时时间（秒）")
    status = Column(Enum(ProviderStatus), default=ProviderStatus.active, nullable=False)
    health_status = Column(Enum(ProviderHealthStatus), default=ProviderHealthStatus.healthy, nullable=False, comment="健康状态")
    last_check_at = Column(DateTime, nullable=True, comment="最后检查时间")
    
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
    
    # 模型列表配置（供应商直接配置，不依赖同步）
    models = Column(Text, nullable=True, comment="模型列表JSON")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
