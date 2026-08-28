"""
操作日志模型
"""
from sqlalchemy import Column, BigInteger, String, DateTime, Text
from sqlalchemy.sql import func

from app.core.database import Base


class OperationLog(Base):
    """操作日志表"""
    __tablename__ = "operation_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    log_id = Column(String(32), unique=True, nullable=False, index=True, comment="业务主键")
    operator_id = Column(String(32), nullable=False, index=True, comment="操作人ID")
    operator_name = Column(String(50), nullable=False, comment="操作人用户名")
    action = Column(String(50), nullable=False, index=True, comment="操作类型")
    target_type = Column(String(50), nullable=False, comment="目标类型")
    target_id = Column(String(32), nullable=True, comment="目标ID")
    detail = Column(Text, nullable=True, comment="详情(JSON)")
    ip_address = Column(String(45), nullable=True, comment="IP地址")
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="操作时间")
