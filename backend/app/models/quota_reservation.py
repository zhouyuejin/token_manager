"""可恢复、可查询的请求预扣及价格快照。"""
from sqlalchemy import Column, String, BigInteger, Numeric, DateTime, Index, Boolean
from app.core.database import Base


class QuotaReservation(Base):
    __tablename__ = 'quota_reservations'
    reservation_id = Column(String(32), primary_key=True)
    user_id = Column(String(32), nullable=False, index=True)
    key_id = Column(String(32), nullable=False, index=True)
    project_id = Column(String(32), nullable=True)
    department_id = Column(String(32), nullable=True)
    model = Column(String(50), nullable=False)
    estimated_tokens = Column(BigInteger, nullable=False)
    actual_tokens = Column(BigInteger, nullable=True)
    estimated_cost_usd = Column(Numeric(18, 8), nullable=False)
    actual_cost_usd = Column(Numeric(18, 8), nullable=True)
    budget_accounted = Column(Boolean, nullable=False, default=True)
    price_type = Column(String(16), nullable=False)
    input_price = Column(Numeric(10, 6), nullable=False)
    output_price = Column(Numeric(10, 6), nullable=False)
    request_price = Column(Numeric(10, 6), nullable=False)
    status = Column(String(16), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    __table_args__ = (Index('ix_reservation_expiry', 'status', 'expires_at'),
                     Index('ix_reservation_project_month', 'project_id', 'created_at'),
                     Index('ix_reservation_department_month', 'department_id', 'created_at'))
