# Spec: Model ↔ Channel 解耦 + 改名 + Failover + 多 Key 轮询

**Status**: Draft
**用户确认决策**:
1. `ModelMapping` → `Model`（类名、表名同步改）
2. `Channel.models` JSON 字段完全删除
3. 其余按设计文档执行（进阶版 failover + 多 key 轮询）

---

## Context

### 现状（已读过源码）

- `Provider` 表同时承担"上游类型"与"具体账户"两层语义，但实际属性（`api_key` 单 key、`endpoint`、quota、sync 等）属于"具体连接"，命名不准。
- `ModelMapping.provider_id` 是 NOT NULL FK，模型被绑死到唯一 provider。`create_provider` 接受 `models` 列表时按 `f"{type}-{model_name}"` 自动生成 `model_id`，当同名模型出现在多个 provider 时直接冲突。
- `proxy_service.get_model_mapping` 取第一个 active mapping 直接返回，`forward_request` 单次失败直接报错；没有 failover。
- `Provider.health_status` 字段存在但无主动检测机制。
- `ProviderQuota`、`usage_logs.provider_id`、`chat_conversations.provider_id` 全部需要跟随重命名。

### 目标

1. **Model 与 Channel 解耦**：Model 可以挂 N 个 Channel，路由时按可用性选择。
2. **`Provider` 改名 `Channel`**：消除命名歧义；属性不变。
3. **`ModelMapping` 改名 `Model`**：类名、表名、schema 同步改。
4. **路由进阶版**：失败自动降级到下一个 channel；区分 4xx（不重试）/ 5xx/超时（重试）。
5. **Channel 多 Key 轮询**：单 key 失败切到 channel 内下一 key，全部失败才触发 channel failover。
6. **删除 `Channel.models` JSON 字段**：原语义由 `model_channels` 关联表表达。
7. **内部使用**：不做对外暴露、不做订阅、不做支付；保留多渠道 failover / 用量同步 / 健康标记。

### 参考实现

new-api（`QuantumNous/new-api`）的核心抽象：
- `Channel` = 一个上游连接（多 key 轮询）
- `Ability` 表 = `(group, model, channel_id)` 三元组 + priority + weight + enabled
- 路由：分层 priority + 同层 weight 随机 + 失败降级

本次取简化版（内部使用）：单 `model_channels` 关联表（去掉 group 维度——本项目已有 ModelGroup 单独的 M:N）、不做 scheduler 自动健康检测（用路由驱动的 cooldown）、key 健康用 channel 表 JSON 字段。

---

## Global Constraints (GC-*)

- **GC-1** — 路由单点：模型分组权限判定仍走 `ProxyService.check_model_group_access` / `get_effective_model_group_ids`（不变）。
- **GC-2** — Channel/Model 改名是全栈改动：Python 类、表、列、FK、路由、schema、API client、前端页面、文案同步；任何遗留的 `provider`/`Provider`/`provider_id`/`providers` 名称视为遗漏。
- **GC-3** — `ModelMapping` → `Model` 包含：类名、表名 `model_mappings → models`、所有引用。`usage_logs.model` 列名是 `model`，与表名重命名无冲突。
- **GC-4** — 失败重试只针对"上游错误"（5xx、超时、连接错误、429）；不针对用户错误（4xx 除 429）。
- **GC-5** — 流式响应不做 failover——一旦 SSE 进入 chunk 迭代，已 yield 给客户端的字节无法撤销。
- **GC-6** — 失败尝试不写 usage_log（避免重复扣费）；全失败时记一行最终 status_code 与最后一次错误信息；失败不扣 user quota。
- **GC-7** — 迁移期 `/admin/providers` 路由保留 308 重定向 + `provider_id` 字段映射读出。
- **GC-8** — 不引入新依赖；保持 Python 3.9 兼容；日志用 loguru。
- **GC-9** — 所有新逻辑必须有 pytest 测试覆盖；现有测试若 fixture 依赖旧 schema 必须改。
- **GC-10** — Channel 类型枚举 (`ChannelType`) 保留 `ProviderType` 的全部值。
- **GC-11** — `cooldown_until` / `key_health` 都是 channel 表字段；不引入新物理表（除了 `model_channels`）。

---

## 数据模型

### channels（替换 providers）

| 列 | 类型 | 备注 |
|---|---|---|
| `id` | BIGINT PK | 自增 |
| `channel_id` | VARCHAR(32) UNIQUE NOT NULL INDEX | 业务主键（前缀 `chan_`） |
| `name` | VARCHAR(50) NOT NULL | |
| `type` | ENUM ChannelType NOT NULL | 枚举值沿用 ProviderType |
| `endpoint` | VARCHAR(255) | |
| `api_key` | VARCHAR(255) NOT NULL | 主 key |
| `extra_keys` | TEXT NULL | JSON 数组，如 `["sk-2","sk-3"]` |
| `key_strategy` | VARCHAR(16) NOT NULL DEFAULT 'round_robin' | `round_robin` \| `random` \| `sequential` |
| `key_health` | TEXT NULL | JSON: `{"<sha256(key)>": {"failure_count": N, "cooldown_until": "ISO8601"}}` |
| `priority` | INT NOT NULL DEFAULT 0 | 数值越大优先级越高 |
| `timeout` | INT NOT NULL DEFAULT 60 | 秒 |
| `status` | ENUM ChannelStatus NOT NULL DEFAULT 'active' | `active` \| `disabled` |
| `health_status` | ENUM ChannelHealthStatus NOT NULL DEFAULT 'healthy' | `healthy` \| `degraded` \| `unhealthy` |
| `last_check_at` | DATETIME NULL | |
| `cooldown_until` | DATETIME NULL | 路由驱动失败降级后屏蔽 |
| `quota_type` | VARCHAR(20) DEFAULT 'none' | `none` \| `unlimited` \| `limited` |
| `quota_hourly` | BIGINT DEFAULT 0 | |
| `quota_weekly` | BIGINT DEFAULT 0 | |
| `sync_enabled` | BOOLEAN DEFAULT FALSE | |
| `sync_interval` | INT DEFAULT 300 | 秒 |
| `last_sync_at` | DATETIME NULL | |
| `quota_config` | TEXT NULL | 自定义用量查询配置 JSON |
| `created_at`, `updated_at` | DATETIME | |

对比现状：删 `models`；增 `extra_keys`, `key_strategy`, `key_health`, `cooldown_until`；`provider_id` → `channel_id`；表 `providers` → `channels`；类 `Provider` → `Channel`

### models（替换 model_mappings）

| 列 | 类型 | 备注 |
|---|---|---|
| `id` | BIGINT PK | 自增 |
| `model_id` | VARCHAR(50) UNIQUE NOT NULL INDEX | 平台对外暴露的 ID |
| `display_name` | VARCHAR(50) NULL | |
| `description` | VARCHAR(255) NULL | |
| `aliases` | TEXT NULL | JSON 数组 |
| `price_type` | ENUM PriceType NOT NULL DEFAULT 'token' | `token` \| `request` |
| `price_per_1k_input` | NUMERIC(10,6) NOT NULL DEFAULT 0 | |
| `price_per_1k_output` | NUMERIC(10,6) NOT NULL DEFAULT 0 | |
| `price_per_request` | NUMERIC(10,6) NOT NULL DEFAULT 0 | |
| `status` | ENUM ModelStatus NOT NULL DEFAULT 'active' | |
| `created_at`, `updated_at` | DATETIME | |

对比现状：删 `provider_id`（NOT NULL FK 去掉）、`provider_model`（搬到 `model_channels.upstream_model`）；表 `model_mappings` → `models`；类 `ModelMapping` → `Model`

### model_channels（新表）

| 列 | 类型 | 备注 |
|---|---|---|
| `id` | BIGINT PK | 自增 |
| `model_id` | VARCHAR(50) NOT NULL INDEX | FK → `models.model_id`, ON DELETE CASCADE |
| `channel_id` | VARCHAR(32) NOT NULL INDEX | FK → `channels.channel_id`, ON DELETE CASCADE |
| `upstream_model` | VARCHAR(50) NOT NULL | 该 channel 上的实际上游模型名 |
| `priority` | INT NOT NULL DEFAULT 0 | model 内 channel 排序权重（缺省回退到 channel.priority） |
| `weight` | INT NOT NULL DEFAULT 100 | 同 priority 内随机权重 |
| `enabled` | TINYINT NOT NULL DEFAULT 1 | |
| `created_at`, `updated_at` | DATETIME | |
| `UNIQUE(model_id, channel_id)` | | |

### 重命名表 / 列

| 表 | 旧 | 新 |
|---|---|---|
| providers | — | channels |
| provider_quotas | — | channel_quotas |
| usage_logs | provider_id | channel_id（FK → channels.channel_id） |
| chat_conversations | provider_id | channel_id（FK → channels.channel_id, ON DELETE SET NULL） |

### 不变的表

- `model_group_model_mappings`（ModelGroup↔Model 的 M:N）
- `users`, `api_keys`, `quota_records`
- 所有 log、notification、refresh_token、system_config 表

---

## 路由 & Failover

### 选 Channel 算法

```
select_channel(db, model_id, user, api_key) → (Channel, upstream_model, key_used) | None:
  1. GC-1: check_model_group_access(api_key, user, model_id) 验证权限；不通过 → None（上层抛 403）
  2. model = db.query(Model).where(model_id == ?, status == active).first()  # 不存在 → None
  3. candidates = (
       db.query(ModelChannel, Channel)
       .join(Channel, Channel.channel_id == ModelChannel.channel_id)
       .where(
         ModelChannel.model_id == model_id,
         ModelChannel.enabled == 1,
         Channel.status == 'active',
         Channel.health_status != 'unhealthy',
         or_(Channel.cooldown_until == None, Channel.cooldown_until < now()),
       )
       .order_by(
         greatest(Channel.priority, ModelChannel.priority).desc(),
         ModelChannel.weight.desc(),
         Channel.channel_id.asc(),
       )
       .all()
     )
  4. if not candidates: return None
  5. (mc, ch) = candidates[0]
  6. key = pick_key(ch)
  7. return (ch, mc.upstream_model, key)
```

### Forward + Failover 算法

```
forward_with_failover(db, model_id, user, api_key, request_data) → Result:
  candidates = select_candidates(db, model_id, user, api_key)  # GC-1 已通过
  if not candidates:
    record_usage_failure(status=502, error="无可用渠道")
    return failure(502, "无可用渠道")

  last_err = None
  attempted_channels: list[str] = []

  for (ch, mc, key) in candidates:
    attempted_channels.append(ch.channel_id)
    try:
      result = forward_one(ch, mc.upstream_model, key, request_data)
      if result.success:
        if ch.channel_id != candidates[0][0].channel_id:
          bump_channel_failure(ch)  # 触发 R7 cooldown
        record_usage(success=True, channel_id=ch.channel_id, ...)
        return result
      elif result.status_code in {400, 401, 403, 404}:
        last_err = result; continue  # 用户/认证错误，跳到下一
      elif result.status_code in {429, 500, 502, 503, 504}:
        bump_key_failure(ch, key)  # 触发 R6 key cooldown
        last_err = result; continue  # 上游错误，跳到下一
      else:
        record_usage(status=result.status_code, channel_id=ch.channel_id, error=result.error)
        return result  # 其它 4xx 不重试
    except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
      bump_key_failure(ch, key)
      last_err = wrap(e, 504); continue

  # 全部失败
  record_usage_failure(
    channel_id=attempted_channels[-1],
    error=f"已尝试 {len(attempted_channels)} 个渠道，全部失败：{last_err.error}"
  )
  return failure(last_err.status_code if last_err else 502,
                 f"已尝试 {len(attempted_channels)} 个渠道，仍失败")
```

### 流式模式（不做 failover）

```
forward_stream(db, model_id, user, api_key, request_data) → stream:
  (ch, mc, key) = select_channel(db, model_id, user, api_key)
  if not ch:
    yield 'data: {"error": "无可用渠道"}\n\n'
    record_usage_failure(status=502, error="无可用渠道"); return
  try:
    yield from forward_stream_one(ch, mc.upstream_model, key, request_data)
  except ...:
    yield 'data: {"error": "..."}\n\n'
    record_usage_failure(channel_id=ch.channel_id, status=504, error=...)
```

---

## 多 Key 轮询

### Key 池

```
key_pool(ch) = [ch.api_key] + (json.loads(ch.extra_keys) if ch.extra_keys else [])
strategy    = ch.key_strategy  # 'round_robin' | 'random' | 'sequential'
```

### pick_key 算法

```
pick_key(ch) → key_str:
  pool = key_pool(ch)
  if not pool: raise ConfigError("channel has no keys")
  health = json.loads(ch.key_health or '{}')
  alive_keys = [k for k in pool if not is_key_in_cooldown(health, k)]
  if not alive_keys:
    alive_keys = pool  # 全 cooldown 时退而求其次

  if ch.key_strategy == 'round_robin':
    counter = get_counter(ch.channel_id)  # 进程级 dict，重启归零
    key = alive_keys[counter % len(alive_keys)]
    incr_counter(ch.channel_id)
    return key
  elif ch.key_strategy == 'random':
    return random.choice(alive_keys)
  else:  # 'sequential'
    return alive_keys[0]
```

### 失败触发

```
bump_key_failure(ch, key) → None:
  health = json.loads(ch.key_health or '{}')
  rec = health.get(sha256(key), {"failure_count": 0, "cooldown_until": None})
  rec["failure_count"] += 1
  if rec["failure_count"] >= 5:
    rec["cooldown_until"] = now() + 60s
    rec["failure_count"] = 0
  health[sha256(key)] = rec
  ch.key_health = json.dumps(health)
  # 不单独 commit——上层 forward_with_failover 整体 commit 时一起持久化

bump_channel_failure(ch) → None:
  ch.cooldown_until = now() + 60s
  # 触发条件：候选 list 中 ch 不是第一个（即实际走了降级）
```

---

## 管理接口

### Channels（替换 `/admin/providers`）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/admin/channels` | 列表（含每 channel 绑定的 models 数） |
| POST | `/api/v1/admin/channels` | 创建 channel，**不**自动建 Model |
| GET | `/api/v1/admin/channels/{id}` | 详情（含 models 绑定清单） |
| PUT | `/api/v1/admin/channels/{id}` | 更新 |
| DELETE | `/api/v1/admin/channels/{id}` | 级联 model_channels；usage_logs / channel_quotas 不级联 |
| GET | `/api/v1/admin/channels/{id}/models` | 该 channel 绑定的 model 列表 |
| POST | `/api/v1/admin/channels/{id}/sync-models` | 一键从 channel 拉模型清单 → 自动建 Model + 自动绑定（fast-path） |

### Models

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/admin/models` | 列表（含每个 model 绑定的 channels 摘要） |
| POST | `/api/v1/admin/models` | 创建 model（无 channel 绑定） |
| GET | `/api/v1/admin/models/{id}` | 详情 + 绑定的 channels |
| PUT | `/api/v1/admin/models/{id}` | 更新（不含 channel 绑定） |
| DELETE | `/api/v1/admin/models/{id}` | 级联 model_channels；usage_logs 历史保留 |
| PUT | `/api/v1/admin/models/{id}/channels` | 整体替换 channel 绑定（事务内） |
| POST | `/api/v1/admin/models/{id}/channels` | 增量添加 channel 绑定 |
| DELETE | `/api/v1/admin/models/{id}/channels/{channel_id}` | 解绑 |
| PATCH | `/api/v1/admin/models/{id}/channels/{channel_id}` | 改 upstream_model / priority / weight / enabled |

### 兼容性

- `GET/POST /api/v1/admin/providers/*` → 308 重定向到 `/api/v1/admin/channels/*`
- `provider_id` 字段读时映射到 `channel_id`（Pydantic alias）
- 迁移期保留 2 个 sprint；之后移除兼容层

---

## 边界处理清单

| 边界 | 策略 |
|---|---|
| Model 未绑任何 enabled channel | select_channel None → 502 "无可用渠道" |
| 绑的 channel 全部 cooldown / health=unhealthy | 同上 |
| Channel quota_hourly 触顶 | 不过滤（本次不做——sync cooldown 留后续） |
| Channel 全部 key 401/403 | 全 channel 失败 → 502/504 + 一条失败 usage_log |
| 流式中途失败 | 不 failover，记一行 status≠200 usage_log |
| Channel.status=disabled | select_channel 过滤 |
| Model.status=disabled | check_model_group_access 过滤 |
| 同一 model 绑同一 channel 两次 | UNIQUE(model_id, channel_id) → 400 |
| ChatConversation.channel_id 迁移前为 provider_id | 迁移时按映射替换；FK 改 ON DELETE SET NULL |
| 删除 channel | model_channels 级联删；usage_logs / channel_quotas 保留 |
| 改 channel.priority 后路由顺序 | 无缓存，下次 select_channel 立即生效 |

---

## Alembic 迁移步骤

**文件**：`backend/alembic/versions/20260910_channels_models_refactor.py`
**revision**: `20260910_channels_models_refactor`
**down_revision**: `20260909_1200_drop_api_key_limit_columns`

### upgrade（顺序严格）

```
1. RENAME TABLE providers TO channels;
   ALTER TABLE channels CHANGE COLUMN provider_id channel_id VARCHAR(32);
   ALTER TABLE channels DROP COLUMN models;
   ALTER TABLE channels ADD COLUMN extra_keys TEXT NULL;
   ALTER TABLE channels ADD COLUMN key_strategy VARCHAR(16) NOT NULL DEFAULT 'round_robin';
   ALTER TABLE channels ADD COLUMN key_health TEXT NULL;
   ALTER TABLE channels ADD COLUMN cooldown_until DATETIME NULL;

2. RENAME TABLE provider_quotas TO channel_quotas;
   ALTER TABLE channel_quotas CHANGE COLUMN provider_id channel_id VARCHAR(32);

3. RENAME TABLE model_mappings TO models;
   ALTER TABLE models MODIFY COLUMN provider_model VARCHAR(50) NULL;

4. ALTER TABLE usage_logs CHANGE COLUMN provider_id channel_id VARCHAR(32);
   ALTER TABLE chat_conversations CHANGE COLUMN provider_id channel_id VARCHAR(32) NULL;

5. CREATE TABLE model_channels (
     id BIGINT PK AUTO_INCREMENT,
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
     INDEX idx_model_enabled (model_id, enabled),
     FOREIGN KEY (model_id) REFERENCES models(model_id) ON DELETE CASCADE,
     FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE CASCADE,
   );

6. INSERT INTO model_channels (model_id, channel_id, upstream_model, enabled, created_at, updated_at)
   SELECT model_id, provider_id, provider_model, 1, NOW(), NOW()
   FROM models
   WHERE provider_id IS NOT NULL;

7. ALTER TABLE models DROP COLUMN provider_id;
   ALTER TABLE models DROP FOREIGN KEY（如有）;
   ALTER TABLE models DROP INDEX（如有）;

8. ALTER TABLE usage_logs ADD FOREIGN KEY (channel_id) REFERENCES channels(channel_id);
   ALTER TABLE chat_conversations ADD FOREIGN KEY (channel_id) REFERENCES channels(channel_id) ON DELETE SET NULL;
   ALTER TABLE channel_quotas ADD FOREIGN KEY (channel_id) REFERENCES channels(channel_id);
```

### downgrade（数据不可完全还原，仅紧急救援）

```
1. ALTER TABLE chat_conversations DROP FOREIGN KEY（如有）;
   ALTER TABLE usage_logs DROP FOREIGN KEY（如有）;
   ALTER TABLE channel_quotas DROP FOREIGN KEY（如有）;
   ALTER TABLE model_channels DROP FOREIGN KEY（如有）;
2. ALTER TABLE chat_conversations CHANGE COLUMN channel_id provider_id VARCHAR(32) NOT NULL;
   ALTER TABLE usage_logs CHANGE COLUMN channel_id provider_id VARCHAR(32) NOT NULL;
   ALTER TABLE channel_quotas CHANGE COLUMN channel_id provider_id VARCHAR(32) NOT NULL;
3. UPDATE models m
   SET m.provider_id = (SELECT channel_id FROM model_channels WHERE model_id = m.model_id LIMIT 1),
       m.provider_model = (SELECT upstream_model FROM model_channels WHERE model_id = m.model_id LIMIT 1);
4. ALTER TABLE models ADD COLUMN provider_id VARCHAR(32) NOT NULL AFTER provider_model;
   ALTER TABLE models MODIFY COLUMN provider_model VARCHAR(50) NOT NULL;
5. DROP TABLE model_channels;
6. RENAME TABLE models TO model_mappings;
7. RENAME TABLE channel_quotas TO provider_quotas;
8. RENAME TABLE channels TO providers;
   ALTER TABLE providers CHANGE COLUMN channel_id provider_id VARCHAR(32);
   ALTER TABLE providers ADD COLUMN models TEXT NULL;
   ALTER TABLE providers DROP COLUMN extra_keys, key_strategy, key_health, cooldown_until;
```

**已知数据丢失**：`providers.models` 字段已删；`models ↔ channels` 多对多关系 downgrade 后坍缩成一对多。回滚只用于紧急救援。

---

## 新增测试文件

```
backend/tests/test_select_channel.py
  - test_orders_by_priority
  - test_orders_by_weight_within_priority
  - test_filters_unhealthy
  - test_filters_cooldown
  - test_returns_none_when_no_candidates
  - test_key_round_robin
  - test_key_random
  - test_key_cooldown_filter

backend/tests/test_failover.py
  - test_first_channel_401_to_second_success
  - test_first_channel_5xx_to_second_success
  - test_user_error_400_no_retry
  - test_all_channels_fail_records_failure
  - test_cooldown_after_threshold
  - test_key_failure_does_not_count_as_channel_failover
  - test_all_keys_fail_triggers_channel_failover

backend/tests/test_multi_key.py
  - test_first_key_401_rotates_to_second
  - test_all_keys_401_triggers_channel_failover
  - test_key_strategy_round_robin_independent_per_channel
  - test_key_cooldown_60s

backend/tests/test_model_channel_crud.py
  - test_create_model_without_channel_binding
  - test_bind_channel_to_model
  - test_unbind_channel_from_model
  - test_patch_model_channel_binding
  - test_unique_constraint_model_channel

backend/tests/test_channel_crud.py
  - test_create_channel_no_auto_model
  - test_update_channel_extra_keys
  - test_delete_channel_cascades_model_channels
  - test_delete_channel_keeps_usage_logs

backend/tests/test_migration_integrity.py
  - test_migration_count_preserved
  - test_migration_upstream_model_preserved
  - test_migration_provider_id_to_channel_id

backend/tests/test_provider_alias.py
  - test_providers_route_redirects_to_channels
  - test_provider_id_field_mapped_to_channel_id
```

现有测试需修：依赖 `provider_id` / `provider` / `usage_log.provider_id` / `chat_conversation.provider_id` 的 fixture 全部改为新名。

---

## Files Touched（预估）

### Backend

```
backend/app/models/__init__.py
backend/app/models/channel.py                        # 新建（Provider → Channel）
backend/app/models/model.py                          # 新建（ModelMapping → Model）
backend/app/models/model_channel.py                   # 新建
backend/app/models/channel_quota.py                  # 新建（ProviderQuota → ChannelQuota）
backend/app/models/usage_log.py                     # 列重命名
backend/app/models/chat.py                          # 列重命名

backend/app/schemas/admin.py                         # Provider→Channel, ModelMapping→Model
backend/app/schemas/chat.py                         # provider_id→channel_id

backend/app/services/proxy_service.py                # select_channel / forward_with_failover / pick_key / bump_*
backend/app/services/sync_service.py                 # provider_quotas→channel_quotas
backend/app/services/scheduler_service.py

backend/app/api/v1/admin.py                          # 所有 provider/model API 改名 + model↔channel 子资源
backend/app/api/v1/proxy.py                         # select_channel 替换
backend/app/api/v1/chat.py                          # 同上 + ChatConversation 字段
backend/app/api/v1/model_groups.py
backend/app/api/v1/stats.py                         # by_provider→by_channel

backend/app/main.py
backend/alembic/versions/20260910_channels_models_refactor.py  # 新建
backend/tests/                                       # 新增 + 修改
```

### Frontend

```
frontend/src/api/providers.ts → channels.ts
frontend/src/api/models.ts                          # 加 channel 子资源
frontend/src/api/chat.ts                            # channel_id
frontend/src/api/stats.ts                           # by_channel

frontend/src/pages/admin/Providers.tsx → Channels.tsx
frontend/src/pages/admin/Models.tsx                 # 增 channels tab
frontend/src/pages/admin/ModelGroups.tsx

frontend/src/pages/Stats.tsx
frontend/src/components/Chat/ModelSelector.tsx     # 展示 channels

frontend/src/App.tsx                                # admin 路由
```

### Docs

```
docs/superpowers/specs/2026-09-09-channel-model-refactor-design.md  # 本文件
docs/API接口设计文档.md
docs/数据库设计文档.md
docs/项目完整文档.md
```

---

## Out of Scope（明确不做）

- Scheduler 自动健康检测（用路由驱动 cooldown 替代）
- Key 级别持久化健康表（用 channel.key_health JSON 字段）
- 对外暴露渠道（无计费、无订阅）
- 流式响应的内部 failover
- 双写兼容（迁移期内单边走新名）
- 灰度发布（一次性切换）
- 并发安全：同一 channel 多 key 被并发请求同时选中（接受 round_robin 自然分布）
