"""平面部门维度。"""
from sqlalchemy import Column, String
from app.core.database import Base


class Department(Base):
    __tablename__ = 'departments'

    dept_id = Column(String(32), primary_key=True)
    name = Column(String(100), nullable=False)
    owner_user_id = Column(String(32), nullable=True)
    status = Column(String(16), nullable=False, default='active')
