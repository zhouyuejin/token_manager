# 内部 Token 中转平台能力补齐计划

> **For agentic workers:** 后续执行本计划时，逐阶段拆成独立任务。每个阶段开始前先复核当前代码和数据库迁移状态，写失败测试，再实现最小改动，最后运行该阶段列出的验证命令。

**Goal:** 将当前 Token Manager 从“可用的内部网关”补齐为“可控、可审计、可归因、可长期运营”的公司级 Token 中转管理平台。

**Architecture:** 继续沿用现有 FastAPI + SQLAlchemy + MySQL + Redis + React/Vite + Ant Design 架构。优先补强现有代理链路、API Key、用户、渠道、模型分组、统计和通知模块，不引入大规模重构；确实需要新边界时，以小服务、小表和清晰接口增加。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL, Redis, React, Vite, Ant Design, pytest, frontend node test/Vite build。

**Reference Docs:** `docs/Token中转平台PRD.md`, `docs/API接口设计文档.md`, `docs/开发计划.md`, `docs/补充设计-用量同步.md`

## 全局约束

- **GC-1:** 简洁优先。只补公司内部平台必须具备的治理能力，不做泛化 SaaS 平台。
- **GC-2:** 不破坏现有 OpenAI-compatible 代理调用、用户登录、模型分组、渠道绑定、配额同步、通知和日志功能。
- **GC-3:** 涉及额度、限流、扣费、Key 安全的改动必须有后端测试覆盖。
- **GC-4:** 涉及后台页面的改动必须至少通过 `cd frontend && npm run build` 或项目当前可用的等价校验；若存在历史 TypeScript 基线错误，必须明确说明验证边界。
- **GC-5:** 所有数据库结构变更必须走 Alembic 迁移，不手改生成后的数据库。
- **GC-6:** 上游密钥、API Key、请求内容、响应内容不得明文写入业务日志或操作日志。
- **GC-7:** 管理员操作必须记录 `operation_logs`；代理调用结果必须继续记录到 `usage_logs`。
- **GC-8:** 优先使用 Redis 做高频、原子、短周期控制；MySQL 保存最终账务、配置和审计事实。
- **GC-9:** 每个阶段都要能独立上线；不要把多个阶段的表结构和行为改动混在一次发布里。

---

## 阶段总览

| 阶段 | 名称 | 主要目标 | 建议优先级 |
| --- | --- | --- | --- |
| Phase 0 | 基线确认与执行护栏 | 明确当前行为、补齐测试入口、避免后续越改越散 | P0 |
| Phase 1 | 访问控制与 API Key 安全 | 补限流、IP 白名单、Key 生命周期、上游密钥加密 | P0 |
| Phase 2 | 额度、预算与账务闭环 | 补预扣、并发安全、对账、部门/项目归因 | P0 |
| Phase 3 | 路由治理与可观测性 | 补健康看板、路由解释、熔断恢复、告警 | P1 |
| Phase 4 | 内部自助与审批 | 补申请、审批、额度/权限自助流程 | P1 |
| Phase 5 | 协议面与企业集成 | 扩展接口协议、SSO/RBAC、合规脱敏、运维能力 | P2 |

---

## 前端补齐总则

后端治理能力只有在用户和管理员可见、可配置、可追踪时才算完整。后续每个 Phase 必须同步检查前端是否需要补齐页面、API 类型、表单、列表字段、操作确认、错误态、空态、权限态和验证命令。

### 前端通用要求

- 新增后端字段时，同步更新 `frontend/src/api/*.ts` 类型和相关页面展示/编辑逻辑。
- 涉及敏感信息时，前端只展示掩码或一次性明文，不在表格、表单回显、通知、日志页中泄露完整 API Key 或上游 Key。
- 涉及阻断类策略时，前端必须能展示明确原因，例如过期、吊销、IP 不匹配、限流、预算不足。
- 涉及管理员动作时，页面必须提供确认和结果反馈，并继续依赖后端操作日志作为审计事实。
- 涉及后台页面的阶段，至少运行 `cd frontend && npm run build`；若新增可独立测试的前端工具函数，补最小 node 测试。
- 视觉和布局改动要复用现有 React/Vite + Ant Design 页面结构，不新增设计系统或复杂状态库。

### 前端状态分层

- 用户自助页：优先补 `frontend/src/pages/ApiKeys.tsx`、`frontend/src/pages/Stats.tsx`、`frontend/src/pages/Notifications.tsx`。
- 管理后台页：优先补 `frontend/src/pages/admin/*.tsx` 和 `frontend/src/pages/AdminDashboard.tsx`。
- API 封装：所有新增接口先进入 `frontend/src/api/*.ts`，页面不直接拼接裸请求。
- 导航入口：新增后台页面必须同步检查 `frontend/src/components/Layout/MainLayout.tsx` 或后台布局入口。

---

## Phase 0: 基线确认与执行护栏

### 目标

建立后续执行的共同基线：当前哪些能力已经工作、哪些只是字段或文档存在、哪些测试命令可用。这个阶段不做产品功能，只做验证和轻量文档更新。

### 当前假设

- 当前项目已有代理转发、API Key、用户、渠道、模型、模型分组、统计、通知、操作日志和登录日志。
- `api_keys.ip_whitelist` 字段存在，但代理认证链路需要再次确认是否真正校验。
- API Key 级 QPS/RPM/TPM 限制目前不是完整能力，需要在 Phase 1 落地。
- 上游渠道密钥目前需要确认是否加密存储；若未加密，Phase 1 必须处理。

### 建议文件

- 修改：`docs/内部Token中转平台能力补齐计划.md`
- 可选新增：`docs/plans/phase-0-baseline-check.md`
- 可选新增：`backend/tests/test_platform_baseline_contract.py`

### 任务

#### Task 0.1: 梳理真实能力清单

**检查点：**
- 路由入口：`frontend/src/App.tsx`
- 后端 API：`backend/app/api/v1/*.py`
- 代理链路：`backend/app/middleware/__init__.py`, `backend/app/api/v1/proxy.py`, `backend/app/services/proxy_service.py`
- 数据模型：`backend/app/models/*.py`
- 管理后台页面：`frontend/src/pages/admin/*.tsx`

**输出：**
- 在本文件或单独文档中标注“已实现 / 字段存在但未接入 / 未实现”。
- 每条结论必须能追溯到文件或测试。

**验收：**
- 后续每个阶段的任务都能引用 Phase 0 的结论。
- 不再把“模型字段存在”误判为“功能链路已完整生效”。

#### Task 0.2: 固定验证命令

**建议命令：**

```bash
cd backend && python -m pytest
cd frontend && npm run build
cd frontend && node src/utils/chatStorage.test.mjs
cd frontend && node src/utils/thinkTag.test.mjs
```

**验收：**
- 记录当前哪些命令通过。
- 若某命令因历史基线失败，记录失败摘要和不影响本阶段的边界。

#### Task 0.3: 建立阶段执行规则

**规则：**
- 每个 Phase 单独开分支或至少单独提交。
- 先写测试再改实现。
- 每个 Phase 完成后更新本计划的状态。
- 不跨 Phase 顺手重构。

**验收：**
- 后续执行可以按 Phase 逐项勾选。

### 不做事项

- 不新增业务表。
- 不改代理行为。
- 不做 UI 调整。

---

## Phase 0 执行记录

### 真实能力清单

| 能力 | 当前状态 | 证据 |
| --- | --- | --- |
| OpenAI-compatible 代理入口 | 已实现 | `backend/app/api/v1/proxy.py` 提供 `/v1/models`、`/v1/balance`、`/v1/chat/completions`，请求进入后读取 `request.state.user` 和 `request.state.api_key`。 |
| 代理 API Key 基础认证 | 已实现 | `backend/app/middleware/__init__.py` 的 `ProxyAuthMiddleware` 只拦截 `/api/v1/proxy/`，调用 `ProxyService.verify_api_key()` 校验 active Key，再调用 `get_user_from_key()` 校验 active 用户。 |
| 模型分组访问控制 | 已实现 | `backend/app/services/proxy_service.py` 的 `check_model_group_access()` 用用户有效分组和模型绑定分组做交集判断。 |
| 用户额度前置检查和调用后扣减 | 已实现但非预扣 | `backend/app/api/v1/proxy.py` 请求前调用 `check_quota()`，成功响应后调用 `deduct_quota()`；当前没有 reservation/rollback 流程。 |
| 代理用量日志 | 已实现 | `backend/app/services/proxy_service.py` 的 `record_usage()` 写入 `usage_logs`，模型见 `backend/app/models/usage_log.py`。 |
| API Key IP 白名单字段存在但代理链路未接入 | 字段存在但未接入 | `backend/app/models/api_key.py` 有 `ip_whitelist`；`backend/app/api/v1/api_keys.py` 的用户/管理员更新接口会保存该字段；`ProxyAuthMiddleware` 目前没有读取或校验客户端 IP。 |
| API Key 级 QPS/RPM/TPM 限流未实现 | 未实现 | `backend/app/models/api_key.py` 已移除 `qps_limit` 等 per-key 限额字段；当前没有 `rate_limit_service.py` 或代理限流调用点。 |
| API Key 生命周期扩展 | 未实现 | `ApiKeyStatus` 只有 `active/disabled`；模型没有 `expires_at`、`revoked_at`、`last_used_ip`、`last_used_user_agent`。 |
| 渠道上游密钥当前按明文字段读取 | 字段存在但未加密 | `backend/app/models/channel.py` 的 `api_key`、`extra_keys` 是普通字符串/JSON 字段；`ProxyService.select_channel()`/`pick_key()` 直接取出 Key 用于上游请求。 |
| 部门/项目/预算归因 | 未实现 | `users`、`api_keys`、`usage_logs` 当前没有 `department_id`/`project_id`/预算字段。 |

### 前端真实能力清单

| 能力 | 当前状态 | 证据 |
| --- | --- | --- |
| 用户侧路由已覆盖统计、通知、API Key、聊天和设置 | 已实现 | `frontend/src/App.tsx` 注册 `/stats`、`/notifications`、`/api-keys`、`/chat`、`/settings`；`MainLayout.tsx` 有对应菜单。 |
| 管理员侧路由已覆盖 dashboard、用户、渠道、模型、模型分组和日志 | 已实现 | `frontend/src/App.tsx` 注册 `/admin/dashboard`、`/admin/users`、`/admin/channels`、`/admin/models`、`/admin/model-groups`、`/admin/logs/operations`、`/admin/logs/logins`；`MainLayout.tsx` 有管理后台菜单。 |
| API Key 页面和 API 类型 | 部分实现 | `frontend/src/api/apiKeys.ts` 已有 `ip_whitelist`、`status`、`last_used_at`；缺少 Phase 1 所需 `expires_at`、`revoked_at`、`revoked_reason`、`last_used_ip`、`last_used_user_agent`、限流字段、轮换/吊销 API 封装。 |
| 渠道页面和 API 类型 | 部分实现且存在安全缺口 | `frontend/src/api/channels.ts` 仍将 `api_key` 声明为普通 `string`，`extra_keys` 为明文数组语义；Phase 1 需要改成掩码/替换语义，避免掩码回写覆盖真实 Key。 |
| 通知、操作日志和登录日志 | 已实现基础入口 | `frontend/src/pages/Notifications.tsx`、`frontend/src/pages/admin/OperationLogs.tsx`、`frontend/src/pages/admin/LoginLogs.tsx` 已存在，可承接后续冻结、审批、审计结果展示。 |
| Phase 1/2 所需的安全、预算、项目和账务页面仍未接入 | 未实现 | 当前没有 `frontend/src/api/billing.ts`、`frontend/src/pages/admin/Billing.tsx`、`Projects.tsx`、`Departments.tsx`，路由和菜单也没有预算/项目/账务入口。 |

### 验证命令基线

| 命令 | 当前结果 | 边界 |
| --- | --- | --- |
| `python -m pytest backend/tests/test_platform_baseline_contract.py -q` | 本机 shell 无 `python` 命令，退出 127。 | 后续本机验证使用 `python3`；容器/CI 若提供 `python` 可继续使用原命令。 |
| `python3 -m pytest backend/tests/test_platform_baseline_contract.py -q` | 通过：`1 passed`。该测试曾先红灯，缺少本执行记录。 | Phase 0 用该测试固定文档基线。 |
| `cd backend && python3 -m pytest` | 未通过：收集期 10 个错误。主要包括无法连接默认 MySQL 主机 `mysql`、多个测试仍导入已不存在的 `app.models.provider`、以及 `migrate_provider_group_bindings_to_models` 旧导入。 | 这是当前后端全量测试基线，不是 Phase 0 改动引入；执行 Phase 1/2 行为改造时必须优先跑目标测试并处理相关基线。 |
| `cd frontend && npm run build` | 通过：`tsc && vite build` 成功，Vite 仅提示 chunk 超过 500 kB。 | Phase 0 不改前端；该结果只证明当前前端可构建。 |
| `cd frontend && node src/utils/chatStorage.test.mjs` | 未通过：5 个子测试均因 Node 直接导入 `chatStorage.ts` 报 `ERR_UNKNOWN_FILE_EXTENSION`。 | 这是测试运行方式/加载器基线问题，不是聊天存储行为验证失败。 |
| `cd frontend && node src/utils/thinkTag.test.mjs` | 通过：`9 passed`。 | Phase 0 不改 think tag 解析逻辑。 |

### 后续执行规则

- Phase 0 不改代理行为，只记录当前事实和护栏。
- Phase 0 前端不做 UI 调整，只记录当前路由、页面、API 类型和验证命令基线。
- Phase 1 才接入 IP 白名单、Key 生命周期、限流和渠道密钥加密。
- Phase 2 才新增部门/项目/预算/预扣/对账相关模型和迁移。
- Phase 1/2 涉及可操作能力时，必须同步补前端 API 类型、页面字段、路由/菜单入口和错误态。
- 每个后续 Phase 先写能红灯的后端测试，再做最小实现，最后更新本计划状态。
- 不跨 Phase 顺手重构；发现无关问题先记录，不在当前阶段处理。

---

## Phase 1: 访问控制与 API Key 安全

### 目标

先把“谁能调用、从哪里调用、调用频率多少、Key 泄露后如何止损、上游密钥是否安全”补齐。这是内部网关上线运营的最低安全底座。

### 主要能力

- API Key IP 白名单真正生效。
- API Key 支持过期时间、轮换、吊销、最后使用信息。
- 按用户/API Key/模型维度限流。
- 上游渠道密钥加密存储和脱敏展示。
- 频繁错误调用自动冻结或降级处理。

### 建议文件

- 修改：`backend/app/models/api_key.py`
- 修改：`backend/app/schemas/api_key.py`
- 修改：`backend/app/api/v1/api_keys.py`
- 修改：`backend/app/middleware/__init__.py`
- 修改：`backend/app/services/proxy_service.py`
- 修改：`backend/app/models/channel.py`
- 修改：`backend/app/api/v1/admin.py`
- 修改：`backend/app/core/config.py`
- 新增：`backend/app/services/rate_limit_service.py`
- 新增：`backend/app/services/secret_crypto.py`
- 新增：`backend/alembic/versions/<timestamp>_api_key_security_and_rate_limits.py`
- 修改：`frontend/src/pages/ApiKeys.tsx`
- 修改：`frontend/src/pages/admin/ChannelForm.tsx`
- 修改：`frontend/src/api/apiKeys.ts`
- 修改：`frontend/src/api/channels.ts`
- 测试：`backend/tests/test_api_key_security.py`
- 测试：`backend/tests/test_proxy_rate_limit.py`
- 测试：`backend/tests/test_channel_secret_crypto.py`

### 数据设计

#### API Key 表补强

建议在 `api_keys` 增加：

- `expires_at`: Key 过期时间，空值表示不过期。
- `revoked_at`: 吊销时间。
- `revoked_reason`: 吊销原因。
- `last_used_ip`: 最后调用 IP。
- `last_used_user_agent`: 最后调用 User-Agent，长度限制，存储前截断。
- `last_error_at`: 最近错误时间。
- `recent_error_count`: 最近错误计数，低频字段可存在 MySQL，高频窗口放 Redis。

#### 限流配置

最小方案先放在 `api_keys` 或新增单表 `api_key_limits`：

- `qps_limit`: 每秒请求数，0 或 null 表示继承用户默认。
- `rpm_limit`: 每分钟请求数。
- `tpm_limit`: 每分钟 token 估算数。
- `concurrency_limit`: 并发请求数。

如果需要用户级默认配置，新增 `user_limits` 或在 `users` 增加限流字段。第一版建议 API Key 优先，用户限流作为全局兜底。

#### 渠道密钥加密

建议不改字段名，先实现读写兼容：

- 新写入的 `channels.api_key` 存加密值。
- `channels.extra_keys` 中每个 Key 存加密值。
- 增加密文前缀，例如 `enc:v1:`，用于区分旧明文。
- 读取时自动识别明文/密文；保存时统一写密文。

### 任务

#### Task 1.1: API Key IP 白名单接入代理链路

**实现：**
- 创建 `ProxyService.check_api_key_ip(api_key, client_ip) -> bool`。
- 在 `ProxyAuthMiddleware.dispatch()` 验证 Key 后校验 IP。
- 支持 CIDR，例如 `10.0.0.0/8`。
- `ip_whitelist` 为空数组或空值时表示不限制。

**验收：**
- 白名单为空：允许调用。
- 请求 IP 命中精确 IP：允许调用。
- 请求 IP 命中 CIDR：允许调用。
- 请求 IP 未命中：返回 403。
- 非法白名单配置不应放行全部，建议忽略非法项并记录操作日志或警告日志。
- 用户和管理员编辑 API Key 时，前端能查看和保存 IP 白名单，空值含义明确。

**验证：**

```bash
cd backend && python -m pytest tests/test_api_key_security.py -v
```

**执行记录：**
- 已新增 `ProxyService.check_api_key_ip(api_key, client_ip) -> bool`，空白名单放行，支持精确 IP 和 CIDR，非法配置不会放行全部。
- 已在 `ProxyAuthMiddleware.dispatch()` 的 Key/User 校验后接入 IP 白名单校验，不命中返回 403。
- 已新增 `backend/tests/test_api_key_security.py` 覆盖空白名单、精确 IP、CIDR、未命中、非法配置、代理中间件允许/拒绝。
- 本机验证命令：`python3 -m pytest backend/tests/test_api_key_security.py -q`，结果 `7 passed`。
- 前端已在 `ApiKeys.tsx` 增加 IP 白名单列表展示、创建表单和编辑表单；支持换行或逗号分隔，留空表示不限制。
- 已新增 `frontend/src/utils/apiKeyWhitelist.ts` 和 `frontend/src/utils/apiKeyWhitelist.test.mjs` 固定白名单文本解析/格式化规则。
- 前端验证命令：`cd frontend && node src/utils/apiKeyWhitelist.test.mjs`，结果 `3 passed`；`cd frontend && npm run build` 通过。

#### Task 1.2: API Key 生命周期管理

**实现：**
- 创建 Key 时允许设置 `expires_at`。
- Key 过期后代理请求返回 401 或 403，错误信息明确为 Key 已过期。
- 支持管理员/用户吊销 Key。
- 轮换 Key 时生成新密钥，旧 Key 可立即吊销；第一版不做灰度双 Key 窗口，避免复杂度。
- API Key 明文只在创建或轮换响应中返回一次。

**前端：**
- `frontend/src/api/apiKeys.ts` 增加 `expires_at`、`revoked_at`、`revoked_reason`、`last_used_ip`、`last_used_user_agent`、`status` 枚举类型。
- `ApiKeys.tsx` 增加过期时间展示。
- 创建弹窗增加过期时间输入，可为空。
- 新 Key 展示后关闭弹窗不再能重新查看完整 Key。
- Key 列表用 Tag 区分 active/disabled/revoked/expired。
- 增加吊销和轮换操作，操作前二次确认，轮换成功后只展示新 Key 一次。
- 管理员视角能看到所属用户、最后使用 IP/User-Agent 和吊销原因。

**验收：**
- 过期 Key 无法调用代理。
- disabled/revoked/expired 三类状态在 UI 和 API 返回中可区分。
- 操作日志记录创建、吊销、轮换。
- API Key 安全状态在列表、详情、创建/编辑/轮换/吊销流程中可见可操作。

**执行记录：**
- 已在 `api_keys` 增加 `expires_at`、`revoked_at`、`revoked_reason`、`last_used_ip`、`last_used_user_agent`，并通过 Alembic 迁移扩展 `status` 为 `active/disabled/revoked`。
- 已新增 `ProxyService.authenticate_api_key()` / `get_api_key_auth_error()`，代理中间件可区分无效、过期、吊销 Key。
- 已扩展 API Key 创建、列表、详情、编辑响应字段；新增用户和管理员吊销/轮换接口。
- 已在 `ApiKeys.tsx` 增加过期时间展示、创建/编辑过期时间、吊销和轮换操作；轮换后的新 Key 仍只展示一次。
- 本机验证命令：`python3 -m pytest backend/tests/test_api_key_security.py backend/tests/test_platform_baseline_contract.py -q`，结果 `13 passed`；`cd frontend && npm run build` 通过。

#### Task 1.3: 限流服务

**实现：**
- 新增 `rate_limit_service.py`。
- 使用 Redis 原子计数实现 QPS/RPM。
- TPM 第一版用请求前估算 tokens；实际 token 仍以 `usage_logs` 为准。
- 并发数使用 Redis increment/decrement，必须在异常路径释放。

**接口：**

```python
class RateLimitDecision(TypedDict):
    allowed: bool
    reason: str
    retry_after_ms: int
    detail: str
```

```python
def check_proxy_rate_limit(
    redis_client,
    api_key,
    model: str,
    estimated_tokens: int,
) -> RateLimitDecision:
    ...
```

**验收：**
- 超 QPS 返回 429。
- 超 RPM 返回 429。
- 超 TPM 返回 429。
- 并发数超限返回 429。
- 上游失败、客户端断开、异常抛出时并发计数会释放。
- API Key 列表或详情能展示当前限流配置；429 错误在调用说明或失败提示中可读。

**执行记录（2026-09-15）：**
- 后端新增 `backend/app/services/rate_limit_service.py`，用 Redis 固定窗口实现 API Key + 模型维度的 QPS/RPM/TPM 计数，并用 Redis 计数实现并发限制。
- `ApiKey` 模型、schema、用户/管理员创建与编辑接口补齐 `qps_limit`、`rpm_limit`、`tpm_limit`、`concurrency_limit`，新增迁移 `20260915_1100_api_key_rate_limits.py`。
- 代理 `/chat/completions` 在 quota 预估后、上游转发前执行限流；超过限制返回 429 和 `Retry-After`，普通响应与流式响应都会释放并发计数。
- 前端 API Key 列表展示限流摘要，创建/编辑弹窗支持设置 QPS/RPM/TPM/并发，`0` 表示不限制。
- 验证：`backend/tests/test_proxy_rate_limit.py` 覆盖 QPS/RPM/TPM/并发阻断与释放；前端通过 `npm run build`。

#### Task 1.4: 上游渠道密钥加密

**实现：**
- `secret_crypto.py` 封装 `encrypt_secret()` / `decrypt_secret()` / `mask_secret()`。
- `SECRET_ENCRYPTION_KEY` 从环境变量读取。
- `ChannelForm` 只展示掩码，不回填明文。
- 后端更新渠道时，空值表示不修改原 Key；新值表示重新加密保存。

**前端：**
- `frontend/src/api/channels.ts` 明确渠道 Key 响应字段为掩码或空值，不声明为完整明文。
- `ChannelForm` 编辑时不把掩码当作真实 Key 提交；Key 输入留空表示不修改。
- 新建渠道时仍要求填写主 Key；编辑渠道时提供“替换 Key”明确动作。
- `Channels.tsx` 列表不得展示完整主 Key 或 extra keys。

**验收：**
- 数据库中新保存的渠道 Key 不再明文可读。
- 旧明文渠道仍能调用，编辑保存后转为密文。
- 列表和详情接口不返回完整上游 Key。
- 测试覆盖明文兼容、密文解密、掩码输出、错误密钥处理。
- 前端不会把掩码回写覆盖真实 Key。

**执行记录（2026-09-15）：**
- 后端新增 `backend/app/services/secret_crypto.py`，使用 `enc:v1:` 前缀区分密文和历史明文；`SECRET_ENCRYPTION_KEY` 可从环境变量读取，未设置时回退使用 `SECRET_KEY` 派生开发密钥。
- 新建渠道时加密保存 `api_key` 和 `extra_keys`；更新渠道时空 `api_key` 表示保持原 Key，新值会重新加密；操作日志中的 Key 改动只记录 `***`。
- 代理转发、模型同步、配额同步在使用渠道 Key 前统一解密，历史明文渠道保持兼容。
- 渠道列表、详情、模型绑定渠道响应只返回掩码 Key，不返回完整上游 Key。
- 前端 `ChannelForm` 编辑态不回填主 Key 和额外 Key；保存时空主 Key 不提交，额外 Key 只有填写 JSON 数组时才替换，避免掩码回写覆盖真实 Key。
- 验证：`python3 -m pytest tests/test_channel_secret_crypto.py tests/test_channel_auth.py tests/test_proxy_service_advanced_config.py tests/test_model_sync_service.py tests/test_channel_quota_windows.py tests/test_admin_channel_advanced.py -q` 通过，`33 passed`；`cd frontend && node src/utils/channelForm.test.mjs && npm run build` 通过。

#### Task 1.5: 错误调用自动冻结

**实现：**
- 记录 API Key 级连续认证失败、额度失败、限流失败、上游 4xx 失败。
- 短时间错误超过阈值时自动 disabled 或进入 cooldown。
- 第一版只冻结明显异常，例如 1 分钟内 50 次认证失败或 IP 不匹配。

**验收：**
- 异常 Key 自动冻结。
- 冻结产生通知给管理员和 Key 所属用户。
- 管理后台可看到冻结原因。
- 用户 API Key 列表和管理员列表能看到自动冻结状态、原因和发生时间。

### Task 1.5 执行记录（2026-09-17）

- **状态：已实现。** Redis Lua 原子记录 API Key 级认证失败、IP 不匹配、额度失败、限流失败和上游 4xx 的 60 秒滚动窗口，以及连续错误类型/次数；成功调用重置连续错误计数，安全异常窗口继续保留。普通/流式上游 4xx 均接入；不存在的密钥无法归属，不累计到其他 Key。
- 第一版仅在 **60 秒内认证失败或 IP 不匹配累计达到 50 次**时自动 `disabled`；额度、限流和上游错误只记录，不触发冻结。Redis 故障保留原请求认证/拒绝结果，不因计数组件故障引入额外阻断。
- 冻结原因、时间、系统操作日志和所属用户/管理员站内通知在同一数据库事务落库。条件更新防止重复冻结和通知；Redis 只保存 Key ID 与密钥指纹，不保存明文密钥、请求或响应内容。
- 用户/管理员 API Key 响应补齐 `frozen_at`、`frozen_reason`，列表只返回掩码 Key。API Key 页面提供管理员“全部 Key”视图，展示所属用户、冻结状态、原因和时间，提供确认后解除冻结。
- 新增管理员 `PUT /api/v1/api-keys/admin/{key_id}/unfreeze`，清理错误计数再启用，保留操作审计；吊销 Key 不可解除为启用。用户启用/轮换以及管理员轮换不得绕过冻结。状态变更使用行锁，认证遇到冻结标记始终拒绝。
- 恢复仓库缺失的 Alembic `20260915_1200_api_key_freeze` 迁移文件。本地数据库已存在这一版本及 `frozen_at/frozen_reason/frozen_until` 字段；兼容保留 `frozen_until`，本任务采用管理员解除冻结，不启用自动到期恢复。`alembic current` 与 `upgrade head` 验证通过，无手工修改数据库。
- 测试先红灯：冻结服务缺失、用户可启用/轮换；审查补充“active 状态仍有冻结标记”的红灯回归后修复。新增测试使用隔离 SQLite 数据库和真实 Redis 随机前缀，测试后删除自身计数器，不调用全库清理 fixture。
- 验证命令：`docker exec token-backend python -m pytest tests/test_api_key_freeze.py tests/test_api_key_security.py tests/test_proxy_rate_limit.py tests/test_proxy_service_advanced_config.py tests/test_proxy_service_admin_override.py tests/test_user_unlimited_quota.py -q`；前端 `cd frontend && npm run build`。结果：**54 passed**；前端 `tsc && vite build` 通过，仅保留既有大包体积提示。`git diff --check` 通过。
- 验证边界：后端包含真实认证中间件/HTTP 权限链路、Redis Lua、普通/流式错误计数和迁移升降级测试；前端为构建验证，未做浏览器交互验收。扩展尝试 `test_proxy_service_model_binding.py` 仍因旧 `app.models.provider` 导入而收集失败，不宣称后端全量通过。

### Phase 1 前端补齐任务

#### Frontend 1.1: API Key 安全配置闭环

**实现：**
- `ApiKeys.tsx` 支持 IP 白名单、过期时间、状态、最后使用信息、吊销、轮换。
- 管理员 API Key 视图支持按用户和状态筛选，显示冻结/吊销/过期原因。
- API Key 明文仅在创建或轮换结果弹窗中展示一次，关闭后只显示掩码。

**验收：**
- 用户能完成创建 Key、设置白名单、设置过期时间、吊销、轮换。
- 管理员能定位某个 Key 的所属用户、安全状态和最近使用来源。
- 前端不会在列表、详情、日志或通知中展示完整 Key。

#### Frontend 1.2: 渠道密钥安全表单

**实现：**
- `ChannelForm` 区分“保持原 Key”和“替换 Key”。
- `extra_keys` 支持逐项替换或清空，避免把 `null`、掩码字符串、空字符串误提交为真实 Key。
- `Channels.tsx` 只展示 Key 数量、掩码或安全状态。

**验收：**
- 编辑渠道但不改 Key 时，原 Key 不被覆盖。
- 替换 Key 后页面显示掩码，不能重新查看完整明文。
- 表单提交 payload 与后端语义一致。

#### Frontend 1.3: 限流和冻结反馈

**实现：**
- API Key 详情展示 QPS/RPM/TPM/并发限制。
- 代理调用相关错误在用户可见位置显示明确原因：IP 不匹配、Key 过期/吊销/冻结、限流。
- 通知详情展示自动冻结原因和解冻/处理建议。

**验收：**
- 429、403、401 的关键原因不会只显示“请求失败”。
- 自动冻结后用户和管理员都能看到状态变化。

### Phase 1 前端补齐执行记录（2026-09-17）

**状态：Frontend 1.1–1.3 已实现，构建和针对性测试通过；登录后的浏览器交互验收待完成。**

- Frontend 1.1：管理员全部 Key 视图增加所属用户与安全状态筛选、管理员安全配置编辑；列表和详情展示最近使用时间/IP、User-Agent、白名单、过期/吊销/冻结信息及四类限流参数。用户可确认启用/禁用；已吊销或自动冻结的 Key 不提供普通启用操作。列表与详情只显示掩码，明文沿用创建/轮换结果弹窗的一次性展示，重新创建时重置结果状态。
- Key 列表每 30 秒以及窗口重新聚焦时刷新，详情跟随当前列表数据更新；加载失败提供重新加载入口。管理员筛选基于当前全量列表，未引入新的服务端分页契约。
- Frontend 1.2：渠道主 Key 区分保持/替换；额外 Key 支持保持、逐项替换/移除、整体替换和清空。前端禁止把 `null`、空字符串或掩码作为真实 Key 提交，保持模式省略对应密钥字段，清空发送 `extra_keys: []`。渠道列表只展示配置状态和额外 Key 数量。
- 为支持逐项修改，`ChannelUpdate` 增加 `extra_key_updates`（原数组索引到新明文或 `null`，`null` 表示移除）；后端保留其他项原密文，新值加密，操作日志只记录 `***`。禁止与整体替换同时提交，非法索引/替换值在写入前拒绝，渠道更新加行锁。列表和详情返回密文列表摘要 `extra_keys_revision`，逐项提交必须携带该版本，过期编辑返回 409，避免并发移除后误改另一项；无需数据库迁移。
- Frontend 1.3：统一 HTTP 错误解析保留 401/403/429 后端原因，同时保留 422 字段校验反馈；聊天普通 HTTP 错误和流内错误对象显示具体原因。冻结通知详情展示原因、按角色提供处理建议及 API Key 管理入口。
- 测试先红后绿：前端先复现非法密钥被接受、逐项更新未转换，以及状态/掩码/错误解析能力缺失；后端先复现逐项更新被忽略、非法索引未拒绝，并补充过期版本拒绝和真实详情 GET → 逐项 PUT → 旧版本 PUT 拒绝的 HTTP 回归测试（使用测试数据库和管理员依赖替换）。
- 前端验证：`node --test frontend/src/utils/security.test.mjs frontend/src/utils/channelForm.test.mjs frontend/src/utils/apiKeyWhitelist.test.mjs`，**12 passed**；`cd frontend && npm run build`，`tsc && vite build` 通过，保留既有大包提示。
- 后端验证：`docker exec token-backend python -m pytest tests/test_channel_secret_crypto.py tests/test_api_key_security.py tests/test_api_key_freeze.py tests/test_admin_channel_advanced.py tests/test_channel_advanced_config_schema.py -q`，**47 passed**，保留既有 Pydantic/SQLAlchemy 警告。`git diff --check` 通过。
- 验证边界：浏览器访问 `http://localhost:3002/api-keys` 被跳转到登录页，未使用凭证登录，未执行创建/轮换/吊销/替换等真实页面操作；不宣称浏览器交互验收或全量后端测试通过。

### 阶段验收

- API Key IP 白名单、过期、吊销、轮换、限流都有后端测试。
- 渠道密钥新写入为密文，接口不泄露明文。
- 代理中间件对安全策略的返回码清晰：401 未认证，403 无权限/IP 不匹配，429 限流。
- 旧数据有兼容路径和迁移说明。
- Phase 1 前端补齐任务完成并通过 `cd frontend && npm run build`。
- API Key 安全状态在列表、详情、创建/编辑/轮换/吊销流程中可见可操作。

### 不做事项

- 不做完整企业 SSO。
- 不做复杂审批流。
- 不做多租户计费结算。

---

## Phase 2: 额度、预算与账务闭环

### 目标

把“额度够不够”和“钱花到哪里了”做成闭环：请求前能挡、请求中能防并发透支、请求后能入账、周期内能对账，管理层能按部门/项目追成本。

### 主要能力

- 预扣费和失败回滚。
- 用户/项目/部门预算。
- 用量按 API Key、用户、项目、部门、模型、渠道归因。
- 账务对账和异常修正。
- 月度/周期报表导出。

### 建议文件

- 修改：`backend/app/models/user.py`
- 修改：`backend/app/models/api_key.py`
- 修改：`backend/app/models/usage_log.py`
- 修改：`backend/app/models/quota_record.py`
- 新增：`backend/app/models/organization.py`
- 新增：`backend/app/models/project.py`
- 新增：`backend/app/models/budget.py`
- 新增：`backend/app/services/quota_reservation_service.py`
- 新增：`backend/app/services/billing_reconcile_service.py`
- 新增：`backend/app/api/v1/billing.py`
- 新增：`backend/alembic/versions/<timestamp>_organization_project_budget.py`
- 修改：`backend/app/services/proxy_service.py`
- 修改：`frontend/src/pages/Stats.tsx`
- 修改：`frontend/src/pages/AdminDashboard.tsx`
- 新增：`frontend/src/pages/admin/Billing.tsx`
- 新增：`frontend/src/api/billing.ts`
- 新增或修改：`frontend/src/pages/admin/Projects.tsx`
- 新增或修改：`frontend/src/pages/admin/Departments.tsx`
- 测试：`backend/tests/test_quota_reservation.py`
- 测试：`backend/tests/test_billing_reconcile.py`
- 测试：`backend/tests/test_org_project_budget.py`

### 数据设计

#### 组织维度

最小可用模型：

- `departments`: `dept_id`, `name`, `owner_user_id`, `status`
- `projects`: `project_id`, `dept_id`, `name`, `owner_user_id`, `status`
- `users.project_ids` 或用户项目关联表
- `api_keys.project_id`: 每个 Key 归属一个项目，便于成本归因

第一版建议 API Key 必须选项目；历史 Key 迁移到默认项目。

#### 预算维度

建议新增 `budgets`：

- `scope_type`: `user` / `project` / `department`
- `scope_id`
- `period`: `daily` / `monthly`
- `amount_usd`
- `used_usd`
- `alert_threshold_percent`
- `status`

#### 预扣记录

建议新增 `quota_reservations`：

- `reservation_id`
- `user_id`
- `key_id`
- `project_id`
- `model`
- `estimated_cost_usd`
- `actual_cost_usd`
- `status`: `reserved` / `committed` / `released` / `expired`
- `created_at`, `updated_at`

### 任务

#### Task 2.1: 项目和部门归因

**实现：**
- 新增部门、项目模型和迁移。
- API Key 创建时必须绑定项目；管理员可为用户分配可用项目。
- `UsageLog` 增加 `project_id`, `department_id`, `cost_usd`。
- 代理记录用量时写入项目和部门。

**验收：**
- 每条新 `usage_logs` 都能追溯到 key/user/project/department/channel/model。
- 旧日志字段为空不影响历史统计。
- 管理后台能按项目筛选用量。
- API Key 创建/编辑前端必须选择项目；历史 Key 显示默认项目或未归因状态。

**执行记录（2026-09-17）：已实现 Task 2.1，浏览器点击验收待完成。**

- 新增 `departments`、`projects`、`user_projects`；管理员通过“部门管理”“项目管理”维护名称、负责人、状态，并在项目中分配用户。
- Key 创建必须提供已授权且启用的 `project_id`；用户和管理员编辑项目时均检查 Key 持有者授权，禁止清空项目。前端创建/编辑必选项目，列表和详情显示项目及部门；轮换保留归属。
- 部门或项目停用、用户项目分配撤销后，已有 Key 保留归属与原有调用能力；前端再次编辑要求重新选择可用项目。运行时项目阻断属于后续策略，不在本任务添加。
- 普通代理、Chat、流式及失败日志保存项目/部门快照和 `Numeric(18, 8)` USD 费用；归属在请求开始时捕获，后续调整不改历史。成功优先采用上游返回的 usage，无 usage 时沿用字符估算；按请求计价模型保存单次价格，失败费用为零。
- 流式保存实际选择的渠道和请求结果，不再把失败记录为成功；确保发给上游的请求包含 `stream=true`。无可用渠道的失败仍保留 `channel_id=NULL`，不虚构渠道。统一补齐其它上游 4xx 的失败日志，避免 Chat 漏记与代理重复记录。
- 管理仪表盘增加项目筛选，全部基础统计、用户/渠道/模型/日维度使用相同过滤条件。新日志使用费用快照；旧 `cost_usd=NULL` 日志保留原有估算方式，两者混合统计不重复计费。
- Alembic：`20260917_1000_project_attribution`，承接 `20260915_1200_api_key_freeze`。历史 Key 迁移默认项目并授权持有人；旧日志归因及成本不回填。兼容当前 `main.py create_all` 已自动创建三张空表的部署状态。部署顺序：先执行迁移，再切换新版后端与前端。
- 本地 MySQL 已执行迁移：2 个历史 Key 均绑定默认项目，49 条旧日志完整保留且新增字段仍为空，2 个持有人获得默认项目授权。真实 HTTP 验证部门/项目/成员/Key/管理统计接口均返回 200；全部统计保留 49 条，按默认项目筛选为 0 条，旧日志未混入。
- 验证：`test_project_attribution.py` 15 项（含迁移升级/降级/再升级、预建表兼容、项目越权、费用混合统计、流式路由实际落库）；与 IP 白名单、冻结和限流测试合计 51 项通过。`cd frontend && npm run build` 通过，存在既有大包提示。
- 验证边界：上游采用 HTTP transport 模拟，未消耗真实模型额度；未做浏览器点击验证，当前电脑控制权限未授予。Task 2.2 预扣费、预算、对账等仍未实现，本记录不代表 Phase 2 整体完成。

#### Task 2.2: 预扣费与并发安全

**实现：**
- 请求进入代理后，根据模型价格和请求内容估算最大成本。
- 使用 Redis 原子扣减可用预算或可用额度。
- 上游成功后提交实际成本。
- 上游失败或本地异常后释放预扣。
- 请求中断时通过超时任务释放过期 `reserved` 记录。

**验收：**
- 并发 20 个请求不会让同一用户额度透支。
- 上游失败不消耗用户额度。
- 成功请求以实际 token 成本入账。
- 预扣和提交均有记录可查。

#### Task 2.3: 预算和阈值告警

**实现：**
- 支持项目/月预算、部门/月预算。
- 达到 80%、90%、100% 阈值时通知项目负责人和管理员。
- 超预算后策略可配置：仅告警或阻断。第一版建议默认阻断。

**验收：**
- 预算低于阈值不通知。
- 首次跨越阈值通知一次。
- 超 100% 后代理请求返回明确错误。
- 通知不会因 WebSocket 失败影响代理主流程。
- 管理后台能配置项目/月预算、部门/月预算、阈值和阻断策略。

#### Task 2.4: 对账任务

**实现：**
- 新增 `billing_reconcile_service.py`。
- 每日扫描前一天 `usage_logs`、`quota_records`、`quota_reservations`。
- 发现 committed 但无 usage log、usage log 无 cost、reserved 过期未释放等异常。
- 第一版只生成对账报告，不自动修账。

**验收：**
- 能输出对账结果：正常、异常数量、异常明细。
- 管理员可在后台查看最近对账结果。
- 异常不会静默吞掉。
- 对账异常可在后台按类型筛选，并能跳转到相关 usage/quota/reservation 记录。

#### Task 2.5: 报表导出

**实现：**
- 新增后端导出接口，支持 CSV。
- 支持筛选：日期范围、部门、项目、用户、模型、渠道。
- 前端后台增加导出按钮。

**验收：**
- 导出的总 token、总成本与页面统计一致。
- 大范围导出有分页或流式策略，不一次性把全部数据加载到内存。
- 前端导出按钮展示处理中、成功、失败状态，失败时保留筛选条件。

### Phase 2 前端补齐任务

#### Frontend 2.1: 部门、项目和 Key 归因管理

**实现：**
- 增加部门/项目管理入口，支持基础增删改查和状态展示。
- 用户管理页能分配可用项目。
- API Key 创建/编辑页必须绑定项目，项目不可用时给出明确提示。

**验收：**
- 管理员能从项目追到部门、负责人、关联用户和关联 Key。
- 普通用户只能选择自己可用项目。
- 历史未归因数据在 UI 中有明确标识，不伪装成已归因。

#### Frontend 2.2: 预算、预扣和成本看板

**实现：**
- `Billing.tsx` 展示预算使用率、预扣中金额、实际消费、剩余预算。
- `Stats.tsx` 和 `AdminDashboard.tsx` 增加项目/部门/模型/渠道成本筛选。
- 对超预算阻断、预扣失败、释放失败展示明确原因。

**验收：**
- 成本归因、预算、预扣、对账和导出必须有后台可操作入口。
- 管理员能回答“哪个部门/项目/Key 花了多少钱”。
- 用户能看到自己 Key/项目的预算剩余和阻断原因。

#### Frontend 2.3: 对账和报表导出

**实现：**
- `Billing.tsx` 增加对账报告列表、异常明细抽屉、CSV 导出。
- 导出沿用当前筛选条件，并展示导出范围摘要。
- 大范围导出时页面不阻塞主交互。

**验收：**
- 对账报告能区分正常、异常、待处理。
- 导出数据口径与页面统计口径一致。
- 导出失败不会清空筛选条件。

### 阶段验收

- 新请求可按部门/项目归因。
- 并发请求不会透支额度。
- 成本统计不再只停留在 token 层面，有 USD 成本闭环。
- 至少有每日对账报告和 CSV 导出。
- Phase 2 前端补齐任务完成并通过 `cd frontend && npm run build`。
- 成本归因、预算、预扣、对账和导出必须有后台可操作入口。

### 不做事项

- 不做发票、付款、采购系统集成。
- 不做复杂成本分摊规则。
- 不做自动修账，先只报告异常。

---

## Phase 3: 路由治理与可观测性

### 目标

让管理员能回答三个问题：请求为什么走这个渠道、为什么失败、现在平台哪里不健康。这个阶段补的是运营效率和故障定位能力。

### 主要能力

- 路由决策解释。
- 渠道、Key、模型维度健康看板。
- 熔断状态和恢复倒计时。
- 延迟、错误率、成功率、成本对比。
- 关键异常告警。

### 建议文件

- 修改：`backend/app/services/proxy_service.py`
- 修改：`backend/app/models/usage_log.py`
- 新增：`backend/app/models/route_decision_log.py`
- 新增：`backend/app/services/route_observability_service.py`
- 新增：`backend/app/api/v1/health.py`
- 修改：`backend/app/services/scheduler_service.py`
- 修改：`backend/app/api/v1/admin.py`
- 修改：`frontend/src/pages/admin/Channels.tsx`
- 新增：`frontend/src/pages/admin/RouteMonitor.tsx`
- 新增：`frontend/src/pages/admin/HealthDashboard.tsx`
- 测试：`backend/tests/test_route_decision_log.py`
- 测试：`backend/tests/test_channel_health_dashboard.py`

### 任务

#### Task 3.1: 路由决策日志

**实现：**
- 每次代理请求记录候选渠道列表、跳过原因、最终选择、失败重试路径。
- 对请求内容做脱敏，不记录 prompt 正文。
- 给每个代理请求生成 `request_id`，返回响应头 `X-Request-ID`。

**验收：**
- 用户报错时，管理员可用 `request_id` 查到路由路径。
- 日志不包含完整 API Key、上游 Key、prompt 正文。
- 成功和失败请求都有可追踪记录。

#### Task 3.2: 渠道健康看板

**实现：**
- 聚合最近 5 分钟、1 小时、24 小时的成功率、错误率、P50/P95 延迟。
- 展示渠道状态、Key cooldown、channel cooldown、最近错误。
- 支持手动恢复 cooldown。

**验收：**
- 一个渠道上游 5xx 增多时，看板能体现错误率上升。
- cooldown 状态可见，恢复时间可见。
- 手动恢复操作写入操作日志。

#### Task 3.3: 路由策略配置

**实现：**
- 在现有 `priority`、`weight` 基础上补明确策略：优先级、权重、最低成本、最低延迟。
- 第一版只支持模型级策略，不做用户级策略。
- 策略应用在 `select_candidates()`。

**验收：**
- 同一模型多个渠道时，可按策略改变候选排序。
- 策略变化有测试覆盖。
- UI 上能看到当前模型/渠道绑定策略。

#### Task 3.4: 告警规则

**实现：**
- 渠道错误率超过阈值通知管理员。
- 上游配额低于阈值通知管理员。
- 单项目用量异常增长通知负责人。
- 第一版用站内通知；邮件/飞书等外部推送放到 Phase 5。

**验收：**
- 告警去重，避免同一问题刷屏。
- 告警恢复时可产生恢复通知。
- 告警规则可在配置中调整阈值。

### Phase 3 前端补齐任务

#### Frontend 3.1: 路由解释和请求定位

**实现：**
- `RouteMonitor.tsx` 支持按 `request_id`、用户、Key、模型、渠道、状态码查询。
- 路由详情展示候选渠道、跳过原因、最终选择、失败重试路径和脱敏后的错误信息。
- 用户报错复制 `request_id` 后，管理员能直接定位到同一条记录。

**验收：**
- 管理员能在 UI 中回答“为什么走这个渠道”和“为什么失败”。
- 页面不展示完整 API Key、上游 Key、prompt 正文。

#### Frontend 3.2: 渠道健康和熔断操作

**实现：**
- `HealthDashboard.tsx` 展示渠道成功率、错误率、P50/P95、cooldown、Key 健康状态。
- `Channels.tsx` 增加健康状态、冷却倒计时和手动恢复入口。
- 手动恢复操作需要确认并展示操作结果。

**验收：**
- 渠道异常、冷却、恢复状态在列表和看板中一致。
- 手动恢复后页面能刷新并体现最新状态。

### 阶段验收

- 管理员可以用 `request_id` 定位一次调用的完整路由过程。
- 渠道健康状态不再只靠列表字段，具备时间窗口指标。
- 熔断/cooldown 可见、可恢复、可审计。
- Phase 3 前端补齐任务完成并通过 `cd frontend && npm run build`。

### 不做事项

- 不自建完整 APM。
- 不接入外部告警渠道。
- 不做复杂策略 DSL。

---

## Phase 4: 内部自助与审批

### 目标

减少管理员手工操作，让普通用户可以申请 Key、额度、模型权限和项目权限；管理员或负责人审批后自动生效，全流程留痕。

### 主要能力

- API Key 申请。
- 额度申请。
- 模型分组权限申请。
- 项目加入申请。
- 审批流、审批记录、通知。

### 建议文件

- 新增：`backend/app/models/approval.py`
- 新增：`backend/app/schemas/approval.py`
- 新增：`backend/app/api/v1/approvals.py`
- 新增：`backend/app/services/approval_service.py`
- 修改：`backend/app/services/notification_service.py`
- 修改：`backend/app/api/v1/api_keys.py`
- 修改：`backend/app/api/v1/admin.py`
- 新增：`frontend/src/pages/Approvals.tsx`
- 新增：`frontend/src/pages/admin/Approvals.tsx`
- 修改：`frontend/src/components/Layout/MainLayout.tsx`
- 测试：`backend/tests/test_approval_service.py`
- 测试：`backend/tests/test_approval_api.py`

### 数据设计

新增 `approval_requests`：

- `request_id`
- `request_type`: `api_key` / `quota` / `model_group` / `project_access`
- `requester_user_id`
- `approver_user_id`
- `target_id`
- `payload`
- `status`: `pending` / `approved` / `rejected` / `cancelled`
- `reason`
- `decision_comment`
- `created_at`, `decided_at`

### 任务

#### Task 4.1: 审批模型和服务

**实现：**
- 创建审批请求。
- 查询我的申请。
- 查询待我审批。
- 审批通过/拒绝。
- 审批通过后调用对应业务动作。

**验收：**
- 重复审批同一请求返回明确错误。
- 申请人不能审批自己的请求，除非是管理员自助场景并明确允许。
- 审批结果写操作日志。

#### Task 4.2: 额度申请

**实现：**
- 普通用户提交额度申请，填写金额和理由。
- 管理员审批通过后调用现有额度调整逻辑。
- 通知申请人审批结果。

**验收：**
- 审批通过后用户额度增加。
- 审批拒绝后额度不变。
- 额度变动记录能追溯到审批单。

#### Task 4.3: 模型权限申请

**实现：**
- 用户申请某模型分组。
- 管理员审批后更新用户 `model_group_ids`。
- 如果该模型分组已停用，审批通过时返回错误。

**验收：**
- 用户获得权限后可调用该组模型。
- 停用分组不能被审批授予。

#### Task 4.4: API Key 申请

**实现：**
- 用户申请创建 Key，填写项目、用途、IP 白名单、过期时间。
- 负责人或管理员审批后创建 Key。
- 完整 Key 明文只展示给申请人一次。

**验收：**
- 未审批前不会创建 Key。
- 审批通过后 Key 归属正确项目。
- Key 安全规则沿用 Phase 1。

### Phase 4 前端补齐任务

#### Frontend 4.1: 用户申请入口

**实现：**
- `Approvals.tsx` 支持普通用户提交 Key、额度、模型分组、项目权限申请。
- 表单复用 Phase 1/2 的安全字段：项目、用途、IP 白名单、过期时间、申请理由。
- 用户能查看我的申请状态、审批意见和生效结果。

**验收：**
- 未审批的申请不会误导用户认为已生效。
- 审批拒绝、取消、补充说明都有明确状态。

#### Frontend 4.2: 管理员审批台

**实现：**
- `admin/Approvals.tsx` 支持按类型、状态、申请人、项目筛选待办。
- 审批详情展示业务影响，例如将增加多少额度、授予哪个模型分组、创建哪个项目 Key。
- 通过/拒绝都需要确认和审批意见。

**验收：**
- 管理员能在一个页面处理所有待审批事项。
- 审批通过后相关业务页面能看到结果。

### 阶段验收

- 用户能自助提交申请。
- 管理员能审批并自动生效。
- 所有审批动作有通知和审计。
- Phase 4 前端补齐任务完成并通过 `cd frontend && npm run build`。

### 不做事项

- 不做多级复杂审批链。
- 不接入企业 IM 审批卡片。
- 不做审批模板配置中心。

---

## Phase 5: 协议面与企业集成

### 目标

在平台治理能力稳定后，再扩展协议覆盖面和企业集成能力。这个阶段不是 MVP 必需，但决定平台能否成为公司统一 AI 入口。

### 主要能力

- 更多 OpenAI-compatible 接口。
- 多供应商格式适配。
- SSO/OIDC/LDAP。
- 更细 RBAC。
- 数据脱敏、请求内容审计策略。
- 备份、恢复、运维健康检查。

### 建议文件

- 修改：`backend/app/api/v1/proxy.py`
- 修改：`backend/app/services/proxy_service.py`
- 新增：`backend/app/services/provider_adapters/`
- 新增：`backend/app/services/content_safety_service.py`
- 新增：`backend/app/services/data_masking_service.py`
- 新增：`backend/app/api/v1/sso.py`
- 新增：`backend/app/models/role_permission.py`
- 修改：`backend/app/dependencies/__init__.py`
- 修改：`frontend/src/App.tsx`
- 修改：`frontend/src/pages/Login.tsx`
- 新增：`frontend/src/pages/admin/Roles.tsx`
- 测试：`backend/tests/test_proxy_responses_api.py`
- 测试：`backend/tests/test_provider_adapters.py`
- 测试：`backend/tests/test_rbac_permissions.py`

### 任务

#### Task 5.1: 扩展代理协议

**优先顺序：**
1. `/v1/responses`
2. `/v1/embeddings`
3. `/v1/images`
4. `/v1/audio/transcriptions`
5. `/v1/rerank` 或供应商私有能力

**实现：**
- 每个接口先支持 OpenAI-compatible 上游。
- 非兼容供应商通过 adapter 转换。
- 用量统计按接口类型记录。

**验收：**
- 每个新增接口有至少一个成功代理测试。
- 不影响现有 `/chat/completions`。
- 统计页能区分接口类型。

#### Task 5.2: Provider Adapter 分层

**实现：**
- 把认证、URL 构造、请求转换、响应转换拆进 adapter。
- 先迁移最常用供应商，不一次性重写全部。
- 保持 `Channel.upstream_format` 兼容。

**验收：**
- 新增一个供应商不需要改大段 `proxy_service.py`。
- 旧渠道配置继续可用。

#### Task 5.3: 企业登录和 RBAC

**实现：**
- 接入 OIDC 或 LDAP，第一版建议 OIDC。
- 保留账号密码登录作为 fallback，是否开放由配置控制。
- 新增角色权限表，拆分平台管理员、部门管理员、审计只读、普通用户。

**验收：**
- OIDC 用户首次登录可自动创建用户。
- 权限控制不再只有 admin/user 二分。
- 审计只读角色不能修改配置。

#### Task 5.4: 数据脱敏和内容审计策略

**实现：**
- 代理日志默认不记录 prompt/response 正文。
- 可配置对请求内容做敏感信息检测或脱敏。
- 管理员可按项目配置是否允许记录摘要。

**验收：**
- 日志中不出现 API Key、身份证号、手机号等明显敏感信息。
- 脱敏规则有测试。
- 请求转发性能不会因脱敏明显下降。

#### Task 5.5: 运维和灾备

**实现：**
- 健康检查覆盖 MySQL、Redis、上游探活、后台任务。
- 数据库备份和恢复文档。
- Prometheus 指标补齐限流、预算、路由、熔断。

**验收：**
- `/health` 能区分 degraded 和 unhealthy。
- 有可执行的恢复步骤文档。
- Grafana 能看到核心运营指标。

### Phase 5 前端补齐任务

#### Frontend 5.1: 协议能力入口

**实现：**
- 模型和渠道页面能区分 chat/responses/embeddings/images/audio/rerank 等接口能力。
- 统计页能按接口类型筛选用量和成本。
- 配置页避免把供应商私有能力混成通用能力。

**验收：**
- 新增代理协议后，管理员能在 UI 中配置和观察对应能力。
- 现有 chat/completions 页面和配置不回退。

#### Frontend 5.2: 企业登录、RBAC 和运维状态

**实现：**
- `Login.tsx` 增加企业登录入口，同时保留账号密码 fallback 策略展示。
- `admin/Roles.tsx` 管理角色和权限，只读角色不展示危险操作按钮。
- 运维健康页展示 MySQL、Redis、上游、后台任务状态。

**验收：**
- 不同角色登录后看到的导航和操作按钮与后端权限一致。
- degraded/unhealthy 状态有明确提示和排查入口。

### 阶段验收

- 平台支持主要 AI 接口类型。
- 用户身份和权限能对接企业体系。
- 数据安全和运维恢复有明确策略。
- Phase 5 前端补齐任务完成并通过 `cd frontend && npm run build`。

### 不做事项

- 不做通用 API 网关产品。
- 不追求支持所有供应商私有能力。
- 不做复杂 DLP 平台，只做必要脱敏和策略入口。

---

## 推荐执行顺序

1. **Phase 0**：先跑一遍基线，不动功能。
2. **Phase 1 Task 1.1-1.3**：先把 IP 白名单、Key 生命周期、限流落地。
3. **Phase 1 Task 1.4**：再做上游密钥加密，避免和限流混在一起。
4. **Phase 2 Task 2.1**：补部门/项目归因，因为后续预算、审批都依赖它。
5. **Phase 2 Task 2.2-2.4**：补预扣、预算、对账。
6. **Phase 3**：补路由可观测和健康看板。
7. **Phase 4**：补审批自助。
8. **Phase 5**：最后做企业集成和协议扩展。

---

## 每阶段完成定义

一个阶段只有同时满足下面条件才算完成：

- 该阶段新增或修改的后端行为有测试。
- 该阶段涉及数据库变更时，有 Alembic migration。
- 该阶段涉及前端时，至少通过前端构建或明确记录历史基线错误。
- 该阶段涉及用户或管理员可操作能力时，前端 API 类型、页面入口、表单/表格字段、错误态和权限态必须同步更新。
- 操作日志、通知、错误码、权限边界都按阶段目标处理。
- 文档更新了实际完成情况和遗留问题。

---

## 风险与取舍

### 风险 1: 一次性做太多导致主链路不稳定

**取舍：** 阶段拆小。先安全和限流，再账务，再可观测，最后审批和企业集成。

### 风险 2: 预扣费估算不准

**取舍：** 第一版允许估算偏保守；成功后按实际 token 结算，多扣部分释放。

### 风险 3: 密钥加密影响旧渠道

**取舍：** 用 `enc:v1:` 前缀兼容旧明文，读取兼容、保存升级。

### 风险 4: 部门/项目模型设计过重

**取舍：** 先只做部门、项目、API Key 归属，不做复杂组织树和成本分摊。

### 风险 5: 审批流过度设计

**取舍：** 第一版只做单级审批，审批通过后调用现有业务接口，不引入流程引擎。

---

## 暂不纳入范围

- 多租户商业化计费。
- 发票、付款、采购流程。
- 多级组织树和复杂成本分摊。
- 外部客户门户。
- 全量 DLP/内容安全平台。
- 自研 APM 或日志平台。
