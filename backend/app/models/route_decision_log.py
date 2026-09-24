"""代理请求路由决策日志。"""
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class RouteDecisionLog(Base):
    __tablename__ = "route_decision_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, index=True)
    user_id = Column(String(32), nullable=True, index=True)
    key_id = Column(String(32), nullable=True, index=True)
    model = Column(String(100), nullable=False, index=True)
    candidate_channels = Column(Text, nullable=False)
    skipped_reasons = Column(Text, nullable=False)
    selected_channel = Column(String(32), nullable=True, index=True)
    retry_path = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=False)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (Index("ix_route_decision_request_created", "request_id", "created_at"),)
