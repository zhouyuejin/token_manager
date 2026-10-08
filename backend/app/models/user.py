"""
用户模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text, Boolean, Integer
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class UserRole(enum.Enum):
    """用户角色"""
    admin = "admin"
    department_admin = "department_admin"
    auditor = "auditor"
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
    nickname = Column(String(50), nullable=True, comment="用户昵称")
    avatar_url = Column(Text, nullable=True, comment="用户头像")
    password = Column(String(255), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    oidc_subject = Column(String(255), unique=True, nullable=True)
    quota = Column(BigInteger, default=0, comment="总额度")
    quota_used = Column(BigInteger, default=0, comment="已使用额度")
    status = Column(Enum(UserStatus), default=UserStatus.active)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime, nullable=True)
    model_group_ids = Column(Text, default='[]', comment="允许使用的模型分组ID列表，JSON数组")
    qps_limit = Column(Integer, default=0, nullable=False, comment="用户每秒请求限制，0表示不限制")
    rpm_limit = Column(Integer, default=0, nullable=False, comment="用户每分钟请求限制，0表示不限制")
    tpm_limit = Column(Integer, default=0, nullable=False, comment="用户每分钟估算Token限制，0表示不限制")
    concurrency_limit = Column(Integer, default=0, nullable=False, comment="用户并发请求限制，0表示不限制")
    
    # 通知设置
    quota_low_alert = Column(Boolean, default=True, comment="额度不足通知")
    quota_change_alert = Column(Boolean, default=True, comment="额度变动通知")
    daily_report = Column(Boolean, default=False, comment="每日用量报表")
