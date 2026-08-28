"""
用量日志模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text
from sqlalchemy.sql import func

from app.core.database import Base


class UsageLog(Base):
    """用量日志表"""
    __tablename__ = "usage_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    log_id = Column(String(32), unique=True, nullable=False, index=True, comment="业务主键")
    user_id = Column(String(32), nullable=False, index=True, comment="用户ID")
    key_id = Column(String(32), nullable=False, index=True, comment="API Key ID")
    provider_id = Column(String(32), nullable=False, index=True, comment="供应商ID")
    model = Column(String(50), nullable=False, index=True, comment="模型名")
    prompt_tokens = Column(Integer, default=0, comment="输入Token数")
    completion_tokens = Column(Integer, default=0, comment="输出Token数")
    total_tokens = Column(Integer, default=0, comment="总Token数")
    latency_ms = Column(Integer, default=0, comment="延迟(毫秒)")
    status_code = Column(Integer, nullable=False, comment="响应状态码")
    error_message = Column(String(500), nullable=True, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), index=True, comment="调用时间")
