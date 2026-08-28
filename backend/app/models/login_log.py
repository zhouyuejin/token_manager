"""
登录日志模型
"""
from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.sql import func

from app.core.database import Base


class LoginLog(Base):
    """登录日志表"""
    __tablename__ = "login_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    log_id = Column(String(32), unique=True, nullable=False, index=True, comment="业务主键")
    username = Column(String(50), nullable=False, index=True, comment="登录尝试的用户名")
    user_id = Column(String(32), nullable=True, index=True, comment="实际命中的用户ID")
    ip_address = Column(String(45), nullable=True, comment="IP地址(兼容IPv6)")
    user_agent = Column(String(500), nullable=True, comment="用户代理")
    status = Column(String(20), nullable=False, index=True, comment="登录状态: success/failed/blocked")
    failure_reason = Column(String(50), nullable=True, comment="失败原因: user_not_found/invalid_password/account_disabled")
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="登录时间")
