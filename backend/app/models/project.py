"""项目及用户授权，不引入组织树。"""
from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Project(Base):
    __tablename__ = 'projects'

    project_id = Column(String(32), primary_key=True)
    dept_id = Column(String(32), ForeignKey('departments.dept_id'), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    owner_user_id = Column(String(32), nullable=True)
    status = Column(String(16), nullable=False, default='active')
    department = relationship('Department')


class UserProject(Base):
    __tablename__ = 'user_projects'

    user_id = Column(String(32), ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True)
    project_id = Column(String(32), ForeignKey('projects.project_id', ondelete='CASCADE'), primary_key=True)
