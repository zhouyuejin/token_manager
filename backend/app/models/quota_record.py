"""
额度变动记录模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class QuotaRecordType(enum.Enum):
    """额度变动类型"""
    increase = "increase"
    decrease = "decrease"


class QuotaRecordSource(enum.Enum):
    """额度变动来源"""
    admin = "admin"
    adjust = "adjust"
    api_call = "api_call"


class QuotaRecord(Base):
    """额度变动记录表"""
    __tablename__ = "quota_records"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_id = Column(String(32), unique=True, nullable=False, index=True, comment="业务主键")
    user_id = Column(String(32), nullable=False, index=True, comment="用户ID")
    type = Column(Enum(QuotaRecordType), nullable=False, comment="变动类型")
    amount = Column(BigInteger, nullable=False, comment="变动数量")
    balance_before = Column(BigInteger, nullable=False, comment="变动前余额")
    balance_after = Column(BigInteger, nullable=False, comment="变动后余额")
    source = Column(String(50), nullable=False, comment="来源")
    reason = Column(String(255), nullable=True, comment="变动原因")
    operator_id = Column(String(32), nullable=True, comment="操作人ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
