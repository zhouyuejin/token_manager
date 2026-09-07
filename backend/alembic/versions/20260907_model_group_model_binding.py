"""model group → model binding

Revision ID: 20260907_mgmb
Revises: c511ac1c9d5f
Create Date: 2026-09-07

将"模型分组 → 供应商"改为"模型分组 → 模型映射"：
- 新增 model_group_model_mappings(group_id, model_id) 多对多表
- 数据迁移：原 provider_model_groups(P, G) 展开为该 P 下每个 ModelMapping 的 (G, model_id)
- 删除 provider_model_groups、api_key_model_groups（API Key 不再保留独立分组权限）

§2 §4 §13 Task 1 实施计划对应。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260907_mgmb'
down_revision: Union[str, None] = 'add_notifications'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. 新表 model_group_model_mappings
    op.create_table(
        'model_group_model_mappings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('group_id', sa.String(32), nullable=False),
        sa.Column('model_id', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['group_id'], ['model_groups.group_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_id'], ['model_mappings.model_id'], ondelete='RESTRICT'),
        sa.UniqueConstraint('group_id', 'model_id', name='uq_model_group_model_mapping'),
    )
    op.create_index(
        'ix_model_group_model_mappings_group_id',
        'model_group_model_mappings',
        ['group_id'],
    )

    # 2. 数据迁移：provider_model_groups → model_group_model_mappings
    rows = bind.execute(sa.text(
        "SELECT pm.group_id, mm.model_id "
        "FROM provider_model_groups pm "
        "JOIN model_mappings mm ON mm.provider_id = pm.provider_id"
    )).fetchall()
    seen = set()
    inserted = 0
    for group_id, model_id in rows:
        if (group_id, model_id) in seen:
            continue
        seen.add((group_id, model_id))
        exists = bind.execute(sa.text(
            "SELECT 1 FROM model_group_model_mappings WHERE group_id=:g AND model_id=:m LIMIT 1"
        ), {"g": group_id, "m": model_id}).first()
        if exists:
            continue
        bind.execute(sa.text(
            "INSERT INTO model_group_model_mappings (group_id, model_id) VALUES (:g, :m)"
        ), {"g": group_id, "m": model_id})
        inserted += 1

    # 3. 删除旧关联表
    op.drop_table('provider_model_groups')
    op.drop_table('api_key_model_groups')


def downgrade() -> None:
    # 1. 重建旧表（空数据 — 不尝试反向展开新表）
    op.create_table(
        'provider_model_groups',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('provider_id', sa.String(32), nullable=False),
        sa.Column('group_id', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.provider_id']),
        sa.ForeignKeyConstraint(['group_id'], ['model_groups.group_id']),
    )
    op.create_table(
        'api_key_model_groups',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('key_id', sa.String(32), nullable=False),
        sa.Column('group_id', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['key_id'], ['api_keys.key_id']),
        sa.ForeignKeyConstraint(['group_id'], ['model_groups.group_id']),
    )

    # 2. 删除新表
    op.drop_index('ix_model_group_model_mappings_group_id', table_name='model_group_model_mappings')
    op.drop_table('model_group_model_mappings')
