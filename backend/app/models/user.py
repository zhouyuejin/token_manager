"""
用户模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class UserRole(enum.Enum):
    """用户角色"""
    admin = "admin"
    user = "user"


class UserStatus(enum.Enum):
    """用户状态"""
    active = "active"
    disabled = "disabled"


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(32), unique=True, nullable=False, index=True, comment="业务主键")
    username = Column(String(50), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    quota = Column(BigInteger, default=0, comment="总额度")
    quota_used = Column(BigInteger, default=0, comment="已使用额度")
    status = Column(Enum(UserStatus), default=UserStatus.active)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime, nullable=True)
