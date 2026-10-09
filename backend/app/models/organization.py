"""平面部门维度。"""
from sqlalchemy import Column, String, Boolean
from app.core.database import Base


class Department(Base):
    __tablename__ = 'departments'

    dept_id = Column(String(32), primary_key=True)
    name = Column(String(100), nullable=False)
    owner_user_id = Column(String(32), nullable=True)
    status = Column(String(16), nullable=False, default='active')
    content_audit_enabled = Column(Boolean, nullable=False, default=False, server_default='0')
