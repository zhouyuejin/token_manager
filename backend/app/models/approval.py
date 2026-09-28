"""单级审批请求。"""
from sqlalchemy import Column, DateTime, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class ApprovalRequest(Base):
    __tablename__ = 'approval_requests'

    request_id = Column(String(32), primary_key=True)
    request_type = Column(String(32), nullable=False, index=True)
    requester_user_id = Column(String(32), nullable=False, index=True)
    approver_user_id = Column(String(32), nullable=True, index=True)
    target_id = Column(String(32), nullable=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(16), nullable=False, default='pending', index=True)
    reason = Column(Text, nullable=False)
    decision_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    decided_at = Column(DateTime, nullable=True)
