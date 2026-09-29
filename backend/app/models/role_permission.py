from sqlalchemy import Column, String

from app.core.database import Base


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role = Column(String(32), primary_key=True)
    permission = Column(String(64), primary_key=True)
