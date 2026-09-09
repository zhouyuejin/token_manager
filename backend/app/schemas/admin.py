"""
管理后台相关Schema
"""
from pydantic import BaseModel, EmailStr, Field, model_validator, computed_field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.schemas._datetime import UtcDateTime


# ========== 用户管理 ==========

class AdminUserCreate(BaseModel):
    """管理员创建用户请求"""
    username: str
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = "user"
    quota: int = 0
    model_group_ids: List[str] = Field(default_factory=list)


class AdminUserUpdate(BaseModel):
    """更新用户请求"""
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    status: Optional[str] = None
    quota: Optional[int] = None
    model_group_ids: Optional[List[str]] = None


class AdminUserResponse(BaseModel):
    """用户响应"""
    user_id: str
    username: str
    email: str
    role: str
    status: str
    quota: int
    quota_used: int
    created_at: UtcDateTime
    model_group_ids: List[str] = Field(default_factory=list)

    @computed_field
    @property
    def unlimited(self) -> bool:
        return self.quota < 0



class UserListResponse(BaseModel):
    """用户列表响应"""
    total: int
    items: List[AdminUserResponse]


class QuotaAdjustRequest(BaseModel):
    """额度调整请求"""
    amount: Optional[int] = None
    set_unlimited: Optional[bool] = None
    reason: str

    @model_validator(mode="after")
    def check_mutual_exclusivity(self):
        if self.set_unlimited is True and self.amount is not None:
            raise ValueError("设为无限制时不能同时指定 amount")
        if self.set_unlimited is None and self.amount is None:
            raise ValueError("必须指定 amount 或 set_unlimited 之一")
        if not self.reason or not self.reason.strip():
            raise ValueError("reason 不能为空")
        return self


# ========== 渠道管理 (Channel) ==========

class QuotaConfig(BaseModel):
    """用量查询自定义配置"""
    model_name: Optional[str] = None
    custom_api_path: Optional[str] = None
    extra_params: Optional[Dict[str, str]] = None


class ChannelCreate(BaseModel):
    """创建渠道请求"""
    name: str
    type: str
    endpoint: str
    api_key: str
    extra_keys: Optional[List[str]] = Field(default=None, description="额外 Key 列表")
    key_strategy: str = "round_robin"
    priority: int = 0
    timeout: int = 60
    quota_type: Optional[str] = "none"
    quota_hourly: Optional[int] = 0
    quota_weekly: Optional[int] = 0
    sync_enabled: Optional[bool] = False
    sync_interval: Optional[int] = 300
    quota_config: Optional[QuotaConfig] = None


class ChannelUpdate(BaseModel):
    """更新渠道请求"""
    name: Optional[str] = None
    type: Optional[str] = None
    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    extra_keys: Optional[List[str]] = None
    key_strategy: Optional[str] = None
    priority: Optional[int] = None
    timeout: Optional[int] = None
    status: Optional[str] = None
    health_status: Optional[str] = None
    quota_type: Optional[str] = None
    quota_hourly: Optional[int] = None
    quota_weekly: Optional[int] = None
    sync_enabled: Optional[bool] = None
    sync_interval: Optional[int] = None
    quota_config: Optional[QuotaConfig] = None


class ChannelResponse(BaseModel):
    """渠道响应"""
    channel_id: str
    name: str
    type: str
    endpoint: str
    api_key: str
    extra_keys: Optional[List[str]] = None
    key_strategy: str = "round_robin"
    priority: int
    timeout: int
    status: str
    health_status: Optional[str] = None
    last_check_at: Optional[UtcDateTime] = None
    cooldown_until: Optional[UtcDateTime] = None
    quota_type: Optional[str] = "none"
    quota_hourly: Optional[int] = 0
    quota_weekly: Optional[int] = 0
    sync_enabled: Optional[bool] = False
    sync_interval: Optional[int] = 300
    last_sync_at: Optional[UtcDateTime] = None
    quota_config: Optional[QuotaConfig] = None
    # 绑定模型数量（列表页聚合）
    bound_models_count: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class ChannelWithModelsResponse(ChannelResponse):
    """渠道响应（含绑定模型列表）"""
    bound_models: List["ModelChannelResponse"] = []


class ChannelListResponse(BaseModel):
    """渠道列表响应"""
    total: int
    items: List[ChannelResponse]


# ========== 兼容性 (Provider alias) ==========

class ProviderCreate(ChannelCreate):
    """兼容旧接口"""
    pass


class ProviderUpdate(ChannelUpdate):
    """兼容旧接口"""
    pass


class ProviderResponse(ChannelResponse):
    """兼容旧接口"""
    
    @classmethod
    def from_channel(cls, channel: ChannelResponse) -> "ProviderResponse":
        """从 ChannelResponse 转换"""
        return cls(**{k: v for k, v in channel.model_dump().items()})


class ProviderListResponse(ChannelListResponse):
    """兼容旧接口"""
    pass


# ========== 模型管理 (Model) ==========

class ModelCreate(BaseModel):
    """创建模型请求"""
    model_id: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    aliases: Optional[List[str]] = None
    price_type: str = "token"
    price_per_1k_input: float = 0
    price_per_1k_output: float = 0
    price_per_request: float = 0
    status: str = "active"


class ModelUpdate(BaseModel):
    """更新模型请求"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    aliases: Optional[List[str]] = None
    price_type: Optional[str] = None
    price_per_1k_input: Optional[float] = None
    price_per_1k_output: Optional[float] = None
    price_per_request: Optional[float] = None
    status: Optional[str] = None


class ModelResponse(BaseModel):
    """模型响应"""
    model_id: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    aliases: Optional[List[str]] = None
    price_type: str = "token"
    price_per_1k_input: float = 0
    price_per_1k_output: float = 0
    price_per_request: float = 0
    status: str
    created_at: Optional[UtcDateTime] = None
    # 绑定渠道数量（列表页聚合）
    bound_channels_count: Optional[int] = None
    # 所属分组
    model_groups: List[str] = Field(default_factory=list, description="所属分组名称列表")



class ModelWithChannelsResponse(ModelResponse):
    """模型响应（含绑定渠道列表）"""
    bound_channels: List["ModelChannelResponse"] = []


class ModelListResponse(BaseModel):
    """模型列表响应"""
    total: int
    items: List[ModelResponse]


# ========== 模型-渠道绑定管理 (ModelChannel) ==========

class ModelChannelCreate(BaseModel):
    """创建模型-渠道绑定"""
    channel_id: str
    upstream_model: str
    priority: int = 0
    weight: int = 100
    enabled: bool = True


class ModelChannelUpdate(BaseModel):
    """更新模型-渠道绑定"""
    upstream_model: Optional[str] = None
    priority: Optional[int] = None
    weight: Optional[int] = None
    enabled: Optional[bool] = None


class ModelChannelResponse(BaseModel):
    """模型-渠道绑定响应"""
    id: int
    model_id: str
    channel_id: str
    upstream_model: str
    priority: int = 0
    weight: int = 100
    enabled: bool = True
    created_at: Optional[UtcDateTime] = None
    # 渠道信息（嵌套）
    channel: Optional[ChannelResponse] = None



# ========== 兼容性 (ModelMapping alias) ==========

class ModelMappingCreate(ModelCreate):
    """兼容旧接口"""
    provider_id: Optional[str] = None  # 忽略
    provider_model: Optional[str] = None  # 忽略


class ModelMappingUpdate(ModelUpdate):
    """兼容旧接口"""
    pass


class ModelMappingResponse(ModelResponse):
    """兼容旧接口"""
    provider_id: Optional[str] = None  # 兼容字段
    provider_model: Optional[str] = None  # 兼容字段


# ========== 渠道配额 (ChannelQuota) ==========

class ChannelQuotaResponse(BaseModel):
    """渠道配额响应"""
    channel_id: str
    channel_name: Optional[str] = None
    hourly: Optional["QuotaDetail"] = None
    weekly: Optional["QuotaDetail"] = None



class QuotaDetail(BaseModel):
    """配额详情"""
    limit: int
    used: int
    remain: int
    percent: float
    reset_at: Optional[str] = None
    last_sync: Optional[str] = None
    raw_data: Optional[Any] = None


class ChannelQuotaListResponse(BaseModel):
    """渠道配额列表响应"""
    total: int
    items: List[ChannelQuotaResponse]


# ========== 用量统计 ==========

class UserUsage(BaseModel):
    """用户用量统计"""
    user_id: str
    username: str
    tokens: int
    requests: int = 0


class ChannelUsage(BaseModel):
    """渠道用量统计"""
    channel: str
    tokens: int
    requests: int = 0


class ModelUsageStats(BaseModel):
    """模型用量统计"""
    model: str
    display_name: Optional[str] = None
    tokens: int
    requests: int
    cost: float = 0


class DailyUsageStats(BaseModel):
    """每日用量统计"""
    date: str
    tokens: int
    requests: int


class AdminStatsResponse(BaseModel):
    """管理员用量统计响应"""
    total_tokens: int = 0
    total_requests: int = 0
    avg_latency_ms: float = 0
    success_rate: float = 100.0
    by_user: List[UserUsage] = []
    by_channel: List[ChannelUsage] = []
    by_model: List[ModelUsageStats] = []
    by_day: List[DailyUsageStats] = []
    
    # 兼容旧字段
    by_provider: List[ChannelUsage] = []


# 解决前向引用
ChannelWithModelsResponse.model_rebuild()
ModelWithChannelsResponse.model_rebuild()
ChannelQuotaResponse.model_rebuild()
