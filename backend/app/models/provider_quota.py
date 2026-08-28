"""
供应商配额模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Numeric
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class QuotaType(enum.Enum):
    """配额类型"""
    hourly = "hourly"
    weekly = "weekly"


class SyncStatus(enum.Enum):
    """同步状态"""
    success = "success"
    failed = "failed"


class ProviderQuota(Base):
    """供应商配额记录表"""
    __tablename__ = "provider_quotas"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider_id = Column(String(32), nullable=False, index=True, comment="供应商ID")
    quota_type = Column(Enum(QuotaType), nullable=False, comment="配额类型")
    quota_limit = Column(BigInteger, default=0, comment="配额限制")
    quota_used = Column(BigInteger, default=0, comment="已使用量")
    quota_remain = Column(BigInteger, default=0, comment="剩余量")
    quota_percent = Column(Numeric(5, 2), default=0, comment="使用百分比")
    sync_status = Column(Enum(SyncStatus), default=SyncStatus.success, comment="同步状态")
    sync_error = Column(String(500), nullable=True, comment="同步错误信息")
    sync_at = Column(DateTime, nullable=False, comment="同步时间")
