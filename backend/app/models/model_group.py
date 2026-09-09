"""
模型分组模型

Task 5: 删除旧 provider_model_groups 和 api_key_model_groups Table 及关联关系。
API Key 不再保留独立分组权限，统一由用户分组决定（§2.15）。
"""
from typing import Optional
from sqlalchemy import Column, BigInteger, String, Enum, DateTime, Text, Table, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
import enum


class ModelGroupStatus(enum.Enum):
    """模型分组状态"""
    active = "active"
    disabled = "disabled"


# 模型分组-模型映射多对多关联表
# 同一 (group_id, model_id) 只能存在一行；删除分组时级联清理关联。
model_group_model_mappings = Table(
    'model_group_model_mappings',
    Base.metadata,
    Column(
        'group_id',
        String(32),
        ForeignKey('model_groups.group_id', ondelete='CASCADE'),
        nullable=False,
    ),
    Column(
        'model_id',
        String(50),
        ForeignKey('models.model_id', ondelete='RESTRICT'),
        nullable=False,
    ),
    Column('created_at', DateTime, server_default=func.now()),
    UniqueConstraint('group_id', 'model_id', name='uq_model_group_model_mapping'),
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

    # 反向关系：与 Model 的多对多
    models = relationship(
        "Model",
        secondary="model_group_model_mappings",
        back_populates="model_groups",
    )



def get_unique_default_group(db) -> Optional["ModelGroup"]:
    """
    返回当前唯一 active 默认分组；若不存在或多于一个则返回 None。
    用于新模型自动绑定判定（避免歧义）。
    """
    defaults = db.query(ModelGroup).filter(
        ModelGroup.is_default == 1,
        ModelGroup.status == ModelGroupStatus.active,
    ).all()
    if len(defaults) != 1:
        return None
    return defaults[0]


def bind_new_model_to_default_group(db, model_mapping) -> None:
    """
    新创建的 ModelMapping 自动绑定到当前唯一默认分组。

    规则（§2.4、§2.5、§2.7、§2.12）：
    - 若没有唯一默认分组 → 不绑定（§2.7）
    - 模型 active/disabled 都会绑定（§2.4）
    - 仅影响新创建的模型，更新已有模型不应调用本函数（§2.6）
    """
    from app.models.model import Model as ModelMapping, ModelStatus as ModelMappingStatus
    default = get_unique_default_group(db)
    if default is None:
        return
    if not isinstance(model_mapping, ModelMapping):
        return
    model_mapping.model_groups.append(default)
