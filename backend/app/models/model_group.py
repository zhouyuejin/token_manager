"""
模型分组模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text, Table, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class ModelGroupStatus(enum.Enum):
    """模型分组状态"""
    active = "active"
    disabled = "disabled"


# 供应商-模型分组关联表
provider_model_groups = Table(
    'provider_model_groups',
    Base.metadata,
    Column('id', BigInteger, primary_key=True, autoincrement=True),
    Column('provider_id', String(32), ForeignKey('providers.provider_id'), nullable=False),
    Column('group_id', String(32), ForeignKey('model_groups.group_id'), nullable=False),
    Column('created_at', DateTime, server_default=func.now())
)


# API Key-模型分组关联表
api_key_model_groups = Table(
    'api_key_model_groups',
    Base.metadata,
    Column('id', BigInteger, primary_key=True, autoincrement=True),
    Column('key_id', String(32), ForeignKey('api_keys.key_id'), nullable=False),
    Column('group_id', String(32), ForeignKey('model_groups.group_id'), nullable=False),
    Column('created_at', DateTime, server_default=func.now())
)


class ModelGroup(Base):
    """模型分组表"""
    __tablename__ = "model_groups"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    group_id = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(50), nullable=False, comment="分组名称")
    description = Column(Text, nullable=True, comment="分组描述")
    status = Column(Enum(ModelGroupStatus), default=ModelGroupStatus.active, nullable=False)
    is_default = Column(BigInteger, default=0, comment="是否为默认分组(1=是,0=否)")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关联
    providers = relationship("Provider", secondary=provider_model_groups, back_populates="model_groups")
    api_keys = relationship("ApiKey", secondary=api_key_model_groups, back_populates="model_groups")
