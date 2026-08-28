"""
模型映射模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class ModelMappingStatus(enum.Enum):
    """模型映射状态"""
    active = "active"
    disabled = "disabled"


class ModelMapping(Base):
    """模型映射表"""
    __tablename__ = "model_mappings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), unique=True, nullable=False, index=True, comment="平台模型ID")
    display_name = Column(String(50), nullable=True, comment="显示名称")
    provider_id = Column(String(32), nullable=False, index=True, comment="关联供应商")
    provider_model = Column(String(50), nullable=False, comment="上游模型名")
    aliases = Column(Text, nullable=True, comment="别名(JSON数组)")
    status = Column(Enum(ModelMappingStatus), default=ModelMappingStatus.active, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
