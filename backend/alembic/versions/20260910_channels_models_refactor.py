"""
channels_models_refactor

将 Provider → Channel, ModelMapping → Model，解除模型与渠道绑定

Revision ID: 20260910_channels_models_refactor
Revises: 20260909_1200_drop_api_key_limit_columns
Create Date: 2026-09-10

执行顺序:
1. RENAME TABLE providers → channels
2. ALTER channels (rename provider_id → channel_id, drop models, add columns)
3. RENAME TABLE provider_quotas → channel_quotas, alter column
4. ALTER usage_logs / chat_conversations (rename provider_id → channel_id)
5. CREATE model_channels
6. INSERT INTO model_channels (from models.provider_id + provider_model)
7. ALTER models (drop provider_id)
8. ADD FOREIGN KEY constraints
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision = '20260910_channels_models_refactor'
down_revision = 'drop_api_key_limit_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === Step 1: RENAME TABLE providers → channels ===
    op.execute("RENAME TABLE providers TO channels")
    
    # === Step 2: ALTER channels ===
    # Rename provider_id → channel_id
    op.execute("ALTER TABLE channels CHANGE COLUMN provider_id channel_id VARCHAR(32) NOT NULL")
    
    # Drop models column
    op.execute("ALTER TABLE channels DROP COLUMN models")
    
    # Add new columns
    op.add_column('channels', sa.Column('extra_keys', sa.Text(), nullable=True))
    op.add_column('channels', sa.Column('key_strategy', sa.String(16), nullable=False, server_default='round_robin'))
    op.add_column('channels', sa.Column('key_health', sa.Text(), nullable=True))
    op.add_column('channels', sa.Column('cooldown_until', sa.DateTime(), nullable=True))
    
    # === Step 3: RENAME TABLE provider_quotas → channel_quotas ===
    op.execute("RENAME TABLE provider_quotas TO channel_quotas")
    op.execute("ALTER TABLE channel_quotas CHANGE COLUMN provider_id channel_id VARCHAR(32) NOT NULL")
    
    # === Step 4: ALTER usage_logs / chat_conversations ===
    op.execute("ALTER TABLE usage_logs CHANGE COLUMN provider_id channel_id VARCHAR(32) NULL")
    op.execute("ALTER TABLE chat_conversations CHANGE COLUMN provider_id channel_id VARCHAR(32) NULL")
    
    # === Step 5: CREATE model_channels ===
    op.execute("""
        CREATE TABLE model_channels (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            model_id VARCHAR(50) NOT NULL,
            channel_id VARCHAR(32) NOT NULL,
            upstream_model VARCHAR(50) NOT NULL,
            priority INT NOT NULL DEFAULT 0,
            weight INT NOT NULL DEFAULT 100,
            enabled TINYINT NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_model_channel (model_id, channel_id),
            INDEX idx_channel_id (channel_id),
            INDEX idx_model_enabled (model_id, enabled)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    
    # === Step 6: INSERT INTO model_channels (数据迁移) ===
    # 从 models.provider_id + models.provider_model 迁移
    op.execute("""
        INSERT INTO model_channels (model_id, channel_id, upstream_model, priority, weight, enabled, created_at, updated_at)
        SELECT model_id, provider_id, COALESCE(provider_model, model_id), 0, 100, 1, NOW(), NOW()
        FROM models
        WHERE provider_id IS NOT NULL AND provider_id != ''
    """)
    
    # === Step 7: ALTER models (drop provider_id) ===
    # 先删除外键约束（如果存在）
    try:
        op.execute("ALTER TABLE models DROP FOREIGN KEY models_ibfk_1")
    except Exception:
        pass  # 外键可能不存在
    
    op.execute("ALTER TABLE models DROP COLUMN provider_id")
    op.execute("ALTER TABLE models DROP INDEX idx_provider_id")
    
    # === Step 8: ADD FOREIGN KEY constraints ===
    op.execute("""
        ALTER TABLE model_channels 
        ADD CONSTRAINT fk_mc_model 
        FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE model_channels 
        ADD CONSTRAINT fk_mc_channel 
        FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE usage_logs 
        ADD CONSTRAINT fk_usage_channel 
        FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE SET NULL
    """)
    op.execute("""
        ALTER TABLE chat_conversations 
        ADD CONSTRAINT fk_chat_channel 
        FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE SET NULL
    """)
    op.execute("""
        ALTER TABLE channel_quotas 
        ADD CONSTRAINT fk_quota_channel 
        FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE CASCADE
    """)


def downgrade() -> None:
    # 注意：数据不可完全还原，仅紧急救援
    
    # === Step 1: DROP FOREIGN KEY constraints ===
    try:
        op.execute("ALTER TABLE model_channels DROP FOREIGN KEY fk_mc_model")
    except Exception:
        pass
    try:
        op.execute("ALTER TABLE model_channels DROP FOREIGN KEY fk_mc_channel")
    except Exception:
        pass
    try:
        op.execute("ALTER TABLE usage_logs DROP FOREIGN KEY fk_usage_channel")
    except Exception:
        pass
    try:
        op.execute("ALTER TABLE chat_conversations DROP FOREIGN KEY fk_chat_channel")
    except Exception:
        pass
    try:
        op.execute("ALTER TABLE channel_quotas DROP FOREIGN KEY fk_quota_channel")
    except Exception:
        pass
    
    # === Step 2: 还原 usage_logs / chat_conversations ===
    op.execute("ALTER TABLE chat_conversations CHANGE COLUMN channel_id provider_id VARCHAR(32) NOT NULL")
    op.execute("ALTER TABLE usage_logs CHANGE COLUMN channel_id provider_id VARCHAR(32) NOT NULL")
    
    # === Step 3: 还原 provider_quotas ===
    op.execute("ALTER TABLE channel_quotas CHANGE COLUMN channel_id provider_id VARCHAR(32) NOT NULL")
    op.execute("RENAME TABLE channel_quotas TO provider_quotas")
    
    # === Step 4: 还原 models 表 ===
    # 添加 provider_id 列（从 model_channels 还原第一条）
    op.execute("""
        ALTER TABLE models 
        ADD COLUMN provider_id VARCHAR(32) NULL AFTER model_id
    """)
    op.execute("""
        UPDATE models m
        SET m.provider_id = (
            SELECT mc.channel_id 
            FROM model_channels mc 
            WHERE mc.model_id = m.model_id 
            LIMIT 1
        )
    """)
    
    # === Step 5: DROP model_channels ===
    op.execute("DROP TABLE model_channels")
    
    # === Step 6: RENAME TABLE ===
    op.execute("RENAME TABLE models TO model_mappings")
    
    # === Step 7: 还原 channels → providers ===
    op.execute("ALTER TABLE channels DROP COLUMN extra_keys")
    op.execute("ALTER TABLE channels DROP COLUMN key_strategy")
    op.execute("ALTER TABLE channels DROP COLUMN key_health")
    op.execute("ALTER TABLE channels DROP COLUMN cooldown_until")
    op.execute("ALTER TABLE channels ADD COLUMN models TEXT NULL")
    op.execute("ALTER TABLE channels CHANGE COLUMN channel_id provider_id VARCHAR(32) NOT NULL")
    op.execute("RENAME TABLE channels TO providers")
