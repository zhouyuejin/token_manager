"""Persistent state for configurable operational alerts."""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.sql import func
from app.core.database import Base

class AlertState(Base):
    __tablename__ = "alert_states"
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_key = Column(String(160), nullable=False)
    alert_type = Column(String(32), nullable=False)
    target_id = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False, default=False)
    last_value = Column(String(64), nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("alert_key", name="uq_alert_state_key"),)
