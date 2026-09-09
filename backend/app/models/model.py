"""
模型配置模型 (Model)

替代原 ModelMapping，支持绑定多个渠道
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class ModelStatus(enum.Enum):
    """模型状态"""
    active = "active"
    disabled = "disabled"


class PriceType(enum.Enum):
    """计费类型"""
    token = "token"  # 按token计费
    request = "request"  # 按请求次数计费


class Model(Base):
    """模型配置表"""
    __tablename__ = "models"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), unique=True, nullable=False, index=True, comment="平台模型ID")
    display_name = Column(String(50), nullable=True, comment="显示名称")
    description = Column(String(255), nullable=True, comment="模型描述")
    aliases = Column(Text, nullable=True, comment="别名(JSON数组)")
    
    # 定价配置
    price_type = Column(Enum(PriceType), default=PriceType.token, nullable=False, comment="计费类型")
    price_per_1k_input = Column(Numeric(10, 6), default=0, nullable=False, comment="每千输入token价格(单位:$)")
    price_per_1k_output = Column(Numeric(10, 6), default=0, nullable=False, comment="每千输出token价格(单位:$)")
    price_per_request = Column(Numeric(10, 6), default=0, nullable=False, comment="每次请求价格(单位:$)")
    
    status = Column(Enum(ModelStatus), default=ModelStatus.active, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    # 与模型分组的多对多关系
    model_groups = relationship(
        "ModelGroup",
        secondary="model_group_model_mappings",
        back_populates="model_mappings",
    )
    
    # 与渠道的多对多关系
    model_channels = relationship("ModelChannel", back_populates="model", cascade="all, delete-orphan")
