"""
模型-渠道关联模型 (ModelChannel)

表达 Model 与 Channel 的多对多关系，包含路由优先级和权重
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ModelChannel(Base):
    """模型-渠道关联表"""
    __tablename__ = "model_channels"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    model_id = Column(String(50), nullable=False, index=True, comment="模型ID")
    channel_id = Column(String(32), nullable=False, index=True, comment="渠道ID")
    upstream_model = Column(String(50), nullable=False, comment="该渠道上的实际上游模型名")
    
    # 路由配置
    priority = Column(Integer, default=0, nullable=False, comment="优先级（数值越大优先级越高）")
    weight = Column(Integer, default=100, nullable=False, comment="权重（相同优先级内随机选择）")
    enabled = Column(Boolean, default=True, nullable=False, comment="是否启用")
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # 关系
    model = relationship("Model", back_populates="model_channels")
    channel = relationship("Channel", back_populates="model_channels")
