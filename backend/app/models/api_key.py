"""
API Key模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class ApiKeyStatus(enum.Enum):
    """API Key状态"""
    active = "active"
    disabled = "disabled"


class ApiKey(Base):
    """API Key表"""
    __tablename__ = "api_keys"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key_id = Column(String(32), unique=True, nullable=False, index=True)
    user_id = Column(String(32), nullable=False, index=True)
    api_key = Column(String(64), unique=True, nullable=False)
    key_name = Column(String(50), nullable=False)
    daily_limit = Column(BigInteger, default=0, comment="单日额度限制(0不限)")
    daily_used = Column(BigInteger, default=0, comment="当日已使用")
    daily_reset_at = Column(DateTime, nullable=True, comment="每日重置日期")
    monthly_limit = Column(BigInteger, default=0, comment="单月额度限制(0不限)")
    monthly_used = Column(BigInteger, default=0, comment="当月已使用")
    monthly_reset_at = Column(DateTime, nullable=True, comment="每月重置日期")
    qps_limit = Column(Integer, default=10, comment="QPS限制")
    ip_whitelist = Column(Text, nullable=True, comment="IP白名单(JSON数组)")
    status = Column(Enum(ApiKeyStatus), default=ApiKeyStatus.active)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime, nullable=True)
    
    # 关联模型分组
    model_groups = relationship("ModelGroup", secondary="api_key_model_groups", back_populates="api_keys")
