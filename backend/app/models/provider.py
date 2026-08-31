"""
供应商模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Integer, Text
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
    name = Column(String(50), nullable=False)
    type = Column(Enum(ProviderType), nullable=False)
    endpoint = Column(String(255), nullable=False)
    api_key = Column(String(255), nullable=False)
    group_id = Column(String(64), nullable=True, comment="供应商Group ID，用于MiniMax等需要分组ID的API")
    priority = Column(Integer, default=100)
    timeout = Column(Integer, default=60)
    status = Column(Enum(ProviderStatus), default=ProviderStatus.active)
    health_status = Column(Enum(ProviderHealthStatus), default=ProviderHealthStatus.healthy)
    last_check_at = Column(DateTime, nullable=True)
    
    # 配额配置
    quota_type = Column(String(20), default="unlimited")
    quota_hourly = Column(BigInteger, default=0)
    quota_weekly = Column(BigInteger, default=0)
    sync_enabled = Column(Integer, default=0)
    sync_interval = Column(Integer, default=300)
    last_sync_at = Column(DateTime, nullable=True)
    
    # 自定义用量查询配置（JSON格式存储）
    # 用于不同供应商不同查询方式时传递自定义参数
    # 结构: {"model_name": "xxx", "custom_api_path": "xxx", "extra_params": {...}}
    quota_config = Column(Text, nullable=True)
    
    # 同步到的模型列表(JSON格式)
    models = Column(Text, nullable=True, comment="同步到的模型列表(JSON数组)")
    last_models_sync_at = Column(DateTime, nullable=True, comment="最后模型同步时间")
    
    # 启用的模型映射ID列表(JSON格式)
    # 存储该供应商可用的模型映射ID
    enabled_models = Column(Text, nullable=True, comment="启用的模型映射ID列表(JSON数组)")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关联模型分组
    model_groups = relationship("ModelGroup", secondary="provider_model_groups", back_populates="providers")
