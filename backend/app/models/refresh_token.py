"""
刷新令牌模型
"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, String, DateTime, Boolean, Index
from sqlalchemy.sql import func

from app.core.database import Base


class RefreshToken(Base):
    """刷新令牌表（明文不存库，只存 SHA256 哈希）"""
    __tablename__ = "refresh_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    token_id = Column(String(32), unique=True, nullable=False, index=True, comment="token 业务 ID")
    user_id = Column(String(32), nullable=False, index=True, comment="用户 ID")
    token_hash = Column(String(64), nullable=False, comment="SHA256(token)")
    expires_at = Column(DateTime, nullable=False, comment="过期时间")
    revoked = Column(Boolean, default=False, nullable=False, comment="是否已撤销")
    revoked_at = Column(DateTime, nullable=True, comment="撤销时间")
    created_at = Column(DateTime, server_default=func.now())
    last_used_at = Column(DateTime, nullable=True, comment="最后一次使用时间")

    __table_args__ = (
        Index("idx_user_revoked", "user_id", "revoked"),
    )
