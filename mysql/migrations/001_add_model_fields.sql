-- 添加模型分组和模型同步相关字段

-- 1. 为 providers 表添加字段
ALTER TABLE providers ADD COLUMN models TEXT NULL COMMENT '同步到的模型列表(JSON数组)' AFTER quota_config;
ALTER TABLE providers ADD COLUMN last_models_sync_at DATETIME NULL COMMENT '最后模型同步时间' AFTER models;

-- 2. 创建模型分组表
CREATE TABLE IF NOT EXISTS model_groups (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    group_id VARCHAR(32) NOT NULL UNIQUE COMMENT '分组ID',
    name VARCHAR(50) NOT NULL COMMENT '分组名称',
    description TEXT NULL COMMENT '分组描述',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态',
    is_default BIGINT DEFAULT 0 COMMENT '是否为默认分组(1=是,0=否)',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_group_id (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型分组表';

-- 3. 创建供应商-模型分组关联表
CREATE TABLE IF NOT EXISTS provider_model_groups (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    provider_id VARCHAR(32) NOT NULL,
    group_id VARCHAR(32) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_provider_id (provider_id),
    INDEX idx_group_id (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='供应商模型分组关联表';

-- 4. 创建API Key-模型分组关联表
CREATE TABLE IF NOT EXISTS api_key_model_groups (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    key_id VARCHAR(32) NOT NULL,
    group_id VARCHAR(32) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_key_id (key_id),
    INDEX idx_group_id (group_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='API Key模型分组关联表';
