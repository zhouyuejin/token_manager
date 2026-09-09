"""
API Key模型

Task 5: 删除 model_groups 关系。
API Key 不再保留独立分组权限，统一由用户分组决定（§2.15）。
GC-9: 删 daily_limit / daily_used / daily_reset_at / monthly_limit / monthly_used / monthly_reset_at / qps_limit。
限流由 User.quota (USD) 统一负责（见 proxy_service.check_quota）。
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text
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
    key_id = Column(String(64), unique=True, nullable=False, index=True, comment="Key ID")
    user_id = Column(String(32), nullable=False, index=True, comment="所属用户")
    api_key = Column(String(64), unique=True, nullable=False, index=True, comment="API Key")
    key_name = Column(String(100), nullable=True, comment="Key名称")

    # IP白名单
    ip_whitelist = Column(Text, nullable=True, comment="IP白名单JSON")
    
    # 状态
    status = Column(Enum(ApiKeyStatus), default=ApiKeyStatus.active, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")
    
    # 关联用户
    user = relationship("User", primaryjoin="foreign(ApiKey.user_id) == User.user_id", viewonly=True)
