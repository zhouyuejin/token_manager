"""按北京时间自然月配置预算，消费从账本计算。"""
from sqlalchemy import Column, String, Numeric, JSON, Boolean, Integer, UniqueConstraint
from app.core.database import Base


class Budget(Base):
    __tablename__ = 'budgets'
    budget_id = Column(String(32), primary_key=True)
    scope_type = Column(String(16), nullable=False)
    scope_id = Column(String(32), nullable=False)
    month = Column(String(7), nullable=False)
    amount_usd = Column(Numeric(18, 8), nullable=False)
    thresholds = Column(JSON, nullable=False)
    policy = Column(String(16), nullable=False, default='block')
    enabled = Column(Boolean, nullable=False, default=True)
    __table_args__ = (UniqueConstraint('scope_type', 'scope_id', 'month', name='uq_budget_scope_month'),)


class BudgetAlert(Base):
    __tablename__ = 'budget_alerts'
    alert_id = Column(String(32), primary_key=True)
    budget_id = Column(String(32), nullable=False)
    threshold = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint('budget_id', 'threshold', name='uq_budget_alert_threshold'),)
