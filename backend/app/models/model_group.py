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



def migrate_provider_group_bindings_to_models(db) -> int:
    """
    将旧 provider_model_groups(provider_id, group_id) 关系展开为新的
    model_group_model_mappings(group_id, model_id) 关系。

    规则：对每一行 (P, G)，找到 provider_id == P 的所有 ModelMapping，
    在新表中插入 (G, model_id)。重复 (G, model_id) 由 UNIQUE 约束去重。

    返回新插入的行数（去重后）。
    """
    from sqlalchemy import text
    rows = db.execute(text(
        "SELECT pm.group_id, mm.model_id "
        "FROM provider_model_groups pm "
        "JOIN model_mappings mm ON mm.provider_id = pm.provider_id"
    )).fetchall()
    inserted = 0
    seen = set()
    for group_id, model_id in rows:
        if (group_id, model_id) in seen:
            continue
        seen.add((group_id, model_id))
        exists = db.execute(text(
            "SELECT 1 FROM model_group_model_mappings "
            "WHERE group_id=:g AND model_id=:m LIMIT 1"
        ), {"g": group_id, "m": model_id}).first()
        if exists:
            continue
        db.execute(text(
            "INSERT INTO model_group_model_mappings (group_id, model_id, created_at) "
            "VALUES (:g, :m, CURRENT_TIMESTAMP)"
        ), {"g": group_id, "m": model_id})
        inserted += 1
    db.commit()
    return inserted


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
