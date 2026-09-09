# Implementation Plan: Model ↔ Channel 解耦 + Failover + 多 Key 轮询

**Status**: Draft  
**Created**: 2026-09-09  
**Based on**: `docs/superpowers/specs/2026-09-09-channel-model-refactor-design.md`

---

## 概览

将 `Provider` → `Channel`，`ModelMapping` → `Model`，解除模型与渠道的绑定关系，引入 `model_channels` 关联表，实现多渠道 failover 和多 key 轮询。

---

## Task 1: Alembic 迁移文件

**文件**: `backend/alembic/versions/20260910_channels_models_refactor.py`

### 变更内容

1. **重命名表**
   - `providers` → `channels`
   - `provider_quotas` → `channel_quotas`

2. **channels 表列变更**
   - `provider_id` → `channel_id`
   - 删除 `models` 列
   - 新增 `extra_keys` (TEXT NULL)
   - 新增 `key_strategy` (VARCHAR(16), DEFAULT 'round_robin')
   - 新增 `key_health` (TEXT NULL)
   - 新增 `cooldown_until` (DATETIME NULL)

3. **model_mappings → models 表**
   - 删除 `provider_id` 列（FK 已移除）
   - `provider_model` 列保留（临时，最终移到 model_channels）

4. **新增 model_channels 表**
   - `id`, `model_id`, `channel_id`, `upstream_model`, `priority`, `weight`, `enabled`, `created_at`, `updated_at`
   - UNIQUE(model_id, channel_id)
   - FK → models(model_id) ON DELETE CASCADE
   - FK → channels(channel_id) ON DELETE CASCADE

5. **usage_logs / chat_conversations 列重命名**
   - `provider_id` → `channel_id`

6. **数据迁移**
   - 从 `models.provider_id` + `models.provider_model` 填充 `model_channels`
   - 迁移完成后删除 `models.provider_id`

### 执行顺序（关键）

```
1. RENAME TABLE
2. ALTER channels (rename provider_id, drop models, add new columns)
3. RENAME TABLE provider_quotas → channel_quotas, alter column
4. ALTER usage_logs / chat_conversations (rename provider_id → channel_id)
5. CREATE model_channels
6. INSERT INTO model_channels (from models.provider_id + provider_model)
7. ALTER models (drop provider_id)
8. ADD FOREIGN KEY constraints
```

### 验证

- [ ] `alembic upgrade --dry-run` 无错误
- [ ] `alembic upgrade` 成功
- [ ] `alembic downgrade` 可回滚（数据丢失可接受）

---

## Task 2: Backend Models

**目录**: `backend/app/models/`

### 新建文件

1. **channel.py** (原 provider.py)
   - 类名: `Channel` (替代 `Provider`)
   - 枚举: `ChannelType`, `ChannelStatus`, `ChannelHealthStatus`
   - 表名: `channels`
   - 新增字段: `extra_keys`, `key_strategy`, `key_health`, `cooldown_until`
   - 移除字段: `models`
   - 关系: `model_channels` (1:N)

2. **model.py** (原 model_mapping.py)
   - 类名: `Model` (替代 `ModelMapping`)
   - 表名: `models`
   - 移除: `provider_id` (NOT NULL FK)
   - 保留: `provider_model` (临时，后续迁移删除)
   - 关系: `model_channels` (1:N)

3. **model_channel.py** (新建)
   - 表名: `model_channels`
   - 字段: `id`, `model_id`, `channel_id`, `upstream_model`, `priority`, `weight`, `enabled`, `created_at`, `updated_at`
   - FK: `model_id` → `models.model_id`
   - FK: `channel_id` → `channels.channel_id`

4. **channel_quota.py** (原 provider_quota.py)
   - 类名: `ChannelQuota`
   - 表名: `channel_quotas`
   - 列: `provider_id` → `channel_id`

### 删除/重命名文件

- 删除: `provider.py`, `model_mapping.py`, `provider_quota.py`
- `__init__.py` 更新导出

### 修改文件

5. **usage_log.py**
   - `provider_id` → `channel_id`

6. **chat.py**
   - `provider_id` → `channel_id` (ChatConversation)

---

## Task 3: Backend Schemas

**文件**: `backend/app/schemas/admin.py`, `backend/app/schemas/chat.py`

### admin.py 变更

1. **Channel 相关 (原 Provider)**
   - `ProviderCreate` → `ChannelCreate`
   - `ProviderUpdate` → `ChannelUpdate`
   - `ProviderResponse` → `ChannelResponse`
   - `ProviderListResponse` → `ChannelListResponse`
   - 新增: `ChannelWithModelsResponse` (包含绑定模型列表)

2. **Model 相关 (原 ModelMapping)**
   - `ModelMappingCreate` → `ModelCreate`
   - `ModelMappingUpdate` → `ModelUpdate`
   - `ModelMappingResponse` → `ModelResponse`
   - `ModelMappingListResponse` → `ModelListResponse`
   - 新增: `ModelWithChannelsResponse`

3. **ModelChannel 相关 (新增)**
   - `ModelChannelCreate`
   - `ModelChannelUpdate`
   - `ModelChannelResponse`

4. **ChannelQuota 相关**
   - `ProviderQuota` → `ChannelQuota`

5. **兼容性**
   - 字段 alias: `provider_id` → `channel_id`

### chat.py 变更

- `provider_id` → `channel_id` in request/response schemas

---

## Task 4: ProxyService 路由层

**文件**: `backend/app/services/proxy_service.py`

### 新增方法

1. **`select_channel(db, model_id, user, api_key)`**
   - 验证权限 (GC-1)
   - 查询 `Model` + `ModelChannel` + `Channel`
   - 按 priority 降序、weight 降序排序
   - 过滤: status='active', health_status!='unhealthy', cooldown_until=null/past
   - 返回: `(Channel, upstream_model, key_used)` 或 `None`

2. **`forward_with_failover(...)`**
   - 调用 `select_channel` 获取候选列表
   - 遍历候选，调用 `forward_one`
   - 4xx (非429): 继续下一 channel
   - 5xx/429/超时: 触发 key/cooldown，继续下一 channel
   - 全失败: 记录一条失败日志，返回 502/504

3. **`pick_key(channel)`**
   - 从 `[api_key] + extra_keys` 池选择
   - 根据 `key_strategy`: round_robin/random/sequential
   - 跳过 cooldown 中的 key

4. **`bump_key_failure(channel, key)`**
   - 更新 `key_health` JSON
   - 5次失败 → 60s cooldown

5. **`bump_channel_failure(channel)`**
   - 设置 `cooldown_until = now() + 60s`
   - 条件: 候选列表中不是第一个

### 修改方法

- `check_model_group_access`: `ModelMapping` → `Model`
- `get_model_mapping`: 移除，改用 `select_channel`
- `record_usage`: `provider_id` → `channel_id`

### 新增属性

```python
# 进程级 round_robin 计数器（重启归零）
_key_sequential_counters: Dict[str, int] = {}
```

---

## Task 5: Backend API Endpoints

**文件**: `backend/app/api/v1/admin.py`, `proxy.py`, `chat.py`, `stats.py`

### admin.py

1. **Channel CRUD** (替换 Provider)
   - `GET /admin/channels` - 列表
   - `POST /admin/channels` - 创建（不自动建 Model）
   - `GET /admin/channels/{id}` - 详情
   - `PUT /admin/channels/{id}` - 更新
   - `DELETE /admin/channels/{id}` - 删除（级联 model_channels）
   - `GET /admin/channels/{id}/models` - 该 channel 绑定的 models
   - `POST /admin/channels/{id}/sync-models` - 一键同步模型

2. **Model CRUD** (替换 ModelMapping)
   - `GET /admin/models` - 列表
   - `POST /admin/models` - 创建（无 channel 绑定）
   - `GET /admin/models/{id}` - 详情
   - `PUT /admin/models/{id}` - 更新
   - `DELETE /admin/models/{id}` - 删除（级联 model_channels）
   - `PUT /admin/models/{id}/channels` - 整体替换 channel 绑定
   - `POST /admin/models/{id}/channels` - 增量添加
   - `DELETE /admin/models/{id}/channels/{channel_id}` - 解绑
   - `PATCH /admin/models/{id}/channels/{channel_id}` - 修改绑定参数

3. **ChannelQuota**
   - `GET /admin/channels/quotas` - 所有渠道配额
   - `GET /admin/channels/{id}/quota` - 单个配额
   - `PUT /admin/channels/{id}/quota` - 更新配额配置
   - `POST /admin/channels/{id}/quota/sync` - 手动同步

### 兼容性路由 (GC-7)

- `GET/POST /admin/providers*` → 308 重定向到 `/admin/channels*`
- `provider_id` 字段 alias 映射

### proxy.py

- 使用 `select_channel` 替代原有逻辑
- 流式请求不做 failover

### chat.py

- `provider_id` → `channel_id`

### stats.py

- `by_provider` → `by_channel`

---

## Task 6: main.py + sync_service + scheduler_service

### main.py

- 更新路由导入
- 更新依赖注入

### sync_service.py

- `Provider` → `Channel`
- `provider_quotas` → `channel_quotas`

### scheduler_service.py

- 更新模型引用

---

## Task 7: 迁移执行

### 步骤

1. **Dry-run 验证**
   ```bash
   cd backend
   alembic upgrade --dry-run
   ```

2. **测试数据库验证**
   - 连接测试数据库
   - 执行迁移
   - 验证数据完整性

3. **生产迁移**
   - 备份数据库
   - 执行迁移
   - 验证

### 回滚方案 (GC-6)

- `alembic downgrade -1`
- 注意：数据丢失（model_channels 数据不可完全还原）

---

## Task 8: 测试

### 新增测试文件

1. **test_select_channel.py**
   - test_orders_by_priority
   - test_orders_by_weight_within_priority
   - test_filters_unhealthy
   - test_filters_cooldown
   - test_returns_none_when_no_candidates
   - test_key_round_robin
   - test_key_random
   - test_key_cooldown_filter

2. **test_failover.py**
   - test_first_channel_401_to_second_success
   - test_first_channel_5xx_to_second_success
   - test_user_error_400_no_retry
   - test_all_channels_fail_records_failure
   - test_cooldown_after_threshold
   - test_key_failure_does_not_count_as_channel_failover
   - test_all_keys_fail_triggers_channel_failover

3. **test_multi_key.py**
   - test_first_key_401_rotates_to_second
   - test_all_keys_401_triggers_channel_failover
   - test_key_strategy_round_robin_independent_per_channel
   - test_key_cooldown_60s

4. **test_model_channel_crud.py**
   - test_create_model_without_channel_binding
   - test_bind_channel_to_model
   - test_unbind_channel_from_model
   - test_patch_model_channel_binding
   - test_unique_constraint_model_channel

5. **test_channel_crud.py**
   - test_create_channel_no_auto_model
   - test_update_channel_extra_keys
   - test_delete_channel_cascades_model_channels
   - test_delete_channel_keeps_usage_logs

6. **test_migration_integrity.py**
   - test_migration_count_preserved
   - test_migration_upstream_model_preserved
   - test_migration_provider_id_to_channel_id

7. **test_provider_alias.py**
   - test_providers_route_redirects_to_channels
   - test_provider_id_field_mapped_to_channel_id

### 现有测试修复

- 所有 fixture 中的 `provider_id` → `channel_id`
- `ModelMapping` → `Model`
- `Provider` → `Channel`

---

## Task 9: Frontend API Client

**目录**: `frontend/src/api/`

### 新建/修改文件

1. **channels.ts** (替换 providers.ts)
   - 接口: `Channel`, `ChannelQuota`
   - API: `getChannels`, `createChannel`, `updateChannel`, `deleteChannel`
   - `getChannelQuota`, `syncChannelQuota`, `updateChannelQuota`
   - `getChannelModels`, `syncChannelModels`

2. **models.ts** (更新)
   - 接口: `Model`, `ModelChannel`
   - 新增: `ModelWithChannels`, `ModelChannelBinding`
   - API: `getModelChannels`, `bindChannelToModel`, `unbindChannel`, `updateModelChannel`

3. **chat.ts**
   - `provider_id` → `channel_id`

4. **stats.ts**
   - `by_provider` → `by_channel`

---

## Task 10: Frontend Pages

**目录**: `frontend/src/pages/admin/`

### 新建/修改文件

1. **Channels.tsx** (替换 Providers.tsx)
   - 列表页
   - 创建/编辑 Modal
   - 配额配置
   - 模型同步

2. **Models.tsx** (更新)
   - 列表页增加 Channels 列
   - 绑定/解绑 Channel
   - 编辑 Channel 绑定参数

3. **App.tsx / router**
   - `/admin/providers` → `/admin/channels` (重定向)
   - 新增 `/admin/models/:id/channels`

---

## Task 11: 最终集成测试 + 提交

### 集成测试

1. **功能测试**
   - [ ] Channel CRUD
   - [ ] Model CRUD + Channel 绑定
   - [ ] 路由: 单 channel 成功
   - [ ] 路由: failover 降级
   - [ ] 路由: 多 key 轮询
   - [ ] 兼容性: /admin/providers 重定向

2. **边界测试**
   - [ ] Model 未绑定 channel → 502
   - [ ] 所有 channel cooldown → 502
   - [ ] 所有 key 失败 → channel failover

### 提交

1. Commit 迁移文件
2. Commit Models + Schemas
3. Commit Services
4. Commit APIs
5. Commit Frontend
6. 清理旧文件

---

## 依赖关系

```
Task 1 (Migration)
    ↓
Task 2 (Models) ← Task 1
    ↓
Task 3 (Schemas) ← Task 2
    ↓
Task 4 (ProxyService) ← Task 2
    ↓
Task 5 (APIs) ← Task 3, Task 4
    ↓
Task 6 (main.py) ← Task 5
    ↓
Task 7 (Migration Run) ← Task 2
    ↓
Task 8 (Tests) ← Task 7
Task 9 (Frontend APIs) ← Task 5
    ↓
Task 10 (Frontend Pages) ← Task 9
    ↓
Task 11 (Final Test + Commit)
```

---

## 边界问题清单

| 边界 | 处理 |
|------|------|
| Model 无绑定 channel | select_channel → None → 502 |
| Channel 全 cooldown | 同上 |
| Channel 全 key 401/403 | channel failover → 502/504 |
| 流式中途失败 | 不 failover，记失败日志 |
| 同 model-channel 重复绑定 | UNIQUE 约束 → 400 |
| 删除 channel | model_channels 级联删，usage_logs 保留 |
| 删除 model | model_channels 级联删，usage_logs.model 保留 |

---

## 不在本次范围 (Out of Scope)

- Scheduler 自动健康检测
- Key 级别持久化健康表
- 流式响应内部 failover
- 灰度发布
