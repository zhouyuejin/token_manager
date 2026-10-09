"""
用量日志模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, Numeric, Index
from sqlalchemy.sql import func

from app.core.database import Base


class UsageLog(Base):
    """用量日志表"""
    __tablename__ = "usage_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    log_id = Column(String(50), unique=True, nullable=False, index=True, comment="日志ID")
    user_id = Column(String(32), nullable=False, index=True, comment="用户ID")
    key_id = Column(String(32), nullable=True, index=True, comment="API Key ID")
    channel_id = Column(String(32), nullable=True, index=True, comment="渠道ID")
    model = Column(String(50), nullable=False, index=True, comment="模型ID")
    api_type = Column(String(32), nullable=False, default="chat", server_default="chat", comment="代理接口类型")
    
    project_id = Column(String(32), nullable=True, index=True, comment="项目快照")
    department_id = Column(String(32), nullable=True, index=True, comment="部门快照")
    cost_usd = Column(Numeric(18, 8), nullable=True, comment="历史原始美元费用，禁止覆写")
    price_currency = Column(String(3), nullable=True)
    exchange_rate = Column(Numeric(18, 8), nullable=True)
    exchange_rate_date = Column(DateTime, nullable=True)
    exchange_rate_source = Column(String(32), nullable=True)
    conversion_kind = Column(String(40), nullable=True)
    cost_cny = Column(Numeric(18, 8), nullable=True, comment="本次费用CNY，旧日志为空")
    reservation_id = Column(String(32), nullable=True, index=True, comment="预扣关联，避免预算重复计费")

    # Token 统计
    prompt_tokens = Column(Integer, default=0, comment="输入Token数")
    completion_tokens = Column(Integer, default=0, comment="输出Token数")
    total_tokens = Column(Integer, default=0, comment="总Token数")
    
    # 性能指标
    latency_ms = Column(Integer, default=0, comment="延迟(毫秒)")
    
    # 状态
    status_code = Column(Integer, nullable=False, comment="HTTP状态码")
    error_message = Column(Text, nullable=True, comment="错误信息")
    request_summary = Column(Text, nullable=True, comment="脱敏后的请求摘要")
    response_summary = Column(Text, nullable=True, comment="脱敏后的响应摘要")
    
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    __table_args__ = (Index('ix_usage_project_month', 'project_id', 'created_at'),
                     Index('ix_usage_department_month', 'department_id', 'created_at'))
