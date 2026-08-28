-- Token中转平台 初始化数据脚本

-- 创建管理员用户 (密码: admin123)
INSERT INTO users (user_id, username, email, password, role, quota, status) 
VALUES ('usr_admin', 'admin', 'admin@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5ePLF3S4f8F3W', 'admin', 100000000, 'active');

-- 创建测试用户 (密码: user123)
INSERT INTO users (user_id, username, email, password, role, quota, status) 
VALUES ('usr_test', 'testuser', 'test@example.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5ePLF3S4f8F3W', 'user', 1000000, 'active');

-- 创建测试API Key
INSERT INTO api_keys (key_id, user_id, api_key, key_name, daily_limit, monthly_limit, qps_limit, status)
VALUES ('key_test001', 'usr_test', 'tmk_test12345678901234567890', '测试Key', 50000, 1000000, 10, 'active');

-- 创建供应商 - 火山方舟
INSERT INTO providers (provider_id, name, type, endpoint, api_key, priority, timeout, status, sync_enabled)
VALUES ('prov_volcengine', '火山方舟', 'volcengine', 'https://ark.cn-beijing.volces.com/api/v3', 'your-volcengine-api-key', 10, 60, 'active', 1);

-- 创建供应商 - OpenAI
INSERT INTO providers (provider_id, name, type, endpoint, api_key, priority, timeout, status, sync_enabled)
VALUES ('prov_openai', 'OpenAI', 'openai', 'https://api.openai.com/v1', 'your-openai-api-key', 20, 60, 'active', 1);

-- 创建供应商 - Anthropic
INSERT INTO providers (provider_id, name, type, endpoint, api_key, priority, timeout, status, sync_enabled)
VALUES ('prov_anthropic', 'Anthropic', 'anthropic', 'https://api.anthropic.com/v1', 'your-anthropic-api-key', 30, 60, 'active', 1);

-- 创建模型映射 - GPT-4
INSERT INTO model_mappings (model_id, display_name, provider_id, provider_model, aliases, status)
VALUES ('gpt-4', 'GPT-4', 'prov_openai', 'gpt-4', '["gpt4","gpt-4-0613"]', 'active');

-- 创建模型映射 - GPT-3.5 Turbo
INSERT INTO model_mappings (model_id, display_name, provider_id, provider_model, aliases, status)
VALUES ('gpt-3.5-turbo', 'GPT-3.5 Turbo', 'prov_openai', 'gpt-3.5-turbo', '["gpt3.5","gpt-3.5-turbo-0613"]', 'active');

-- 创建模型映射 - Claude
INSERT INTO model_mappings (model_id, display_name, provider_id, provider_model, aliases, status)
VALUES ('claude-3-opus', 'Claude 3 Opus', 'prov_anthropic', 'claude-3-opus-20240229', '["claude","claude-3"]', 'active');

-- 创建模型映射 - 火山方舟
INSERT INTO model_mappings (model_id, display_name, provider_id, provider_model, aliases, status)
VALUES ('doubao-pro-32k', '豆包Pro 32K', 'prov_volcengine', 'doubao-pro-32k', '["doubao","豆包"]', 'active');

-- 创建系统配置
INSERT INTO system_configs (config_key, config_value, description)
VALUES 
('site_name', 'Token中转平台', '网站名称'),
('site_description', '统一API入口，管理大模型调用', '网站描述'),
('default_quota', '1000000', '新用户默认额度'),
('quota_warning_percent', '20', '额度预警百分比');
