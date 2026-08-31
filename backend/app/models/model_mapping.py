"""
模型映射模型
"""
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text, Numeric
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class ModelMappingStatus(enum.Enum):
    """模型映射状态"""
    active = "active"
    disabled = "disabled"


class PriceType(enum.Enum):
    """计费类型"""
    token = "token"  # 按token计费
    request = "request"  # 按请求次数计费


class ModelMapping(Base):
    """模型映射表（也作为统一模型配置）"""
    __tablename__ = "model_mappings"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), unique=True, nullable=False, index=True, comment="平台模型ID")
    display_name = Column(String(50), nullable=True, comment="显示名称")
    description = Column(String(255), nullable=True, comment="模型描述")
    provider_id = Column(String(32), nullable=False, index=True, comment="关联供应商")
    provider_model = Column(String(50), nullable=False, comment="上游模型名")
    aliases = Column(Text, nullable=True, comment="别名(JSON数组)")
    
    # 定价配置
    price_type = Column(Enum(PriceType), default=PriceType.token, nullable=False, comment="计费类型")
    price_per_1k_input = Column(Numeric(10, 4), default=0, nullable=False, comment="每千输入token价格(单位:元)")
    price_per_1k_output = Column(Numeric(10, 4), default=0, nullable=False, comment="每千输出token价格(单位:元)")
    price_per_request = Column(Numeric(10, 4), default=0, nullable=False, comment="每次请求价格(单位:元)")
    
    status = Column(Enum(ModelMappingStatus), default=ModelMappingStatus.active, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
