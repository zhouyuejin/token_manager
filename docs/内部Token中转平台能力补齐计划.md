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

**验证：**

```bash
cd backend && python -m pytest tests/test_api_key_security.py -v
```

#### Task 1.2: API Key 生命周期管理

**实现：**
- 创建 Key 时允许设置 `expires_at`。
- Key 过期后代理请求返回 401 或 403，错误信息明确为 Key 已过期。
- 支持管理员/用户吊销 Key。
- 轮换 Key 时生成新密钥，旧 Key 可立即吊销；第一版不做灰度双 Key 窗口，避免复杂度。
- API Key 明文只在创建或轮换响应中返回一次。

**前端：**
- `ApiKeys.tsx` 增加过期时间展示。
- 创建弹窗增加过期时间输入，可为空。
- 新 Key 展示后关闭弹窗不再能重新查看完整 Key。

**验收：**
- 过期 Key 无法调用代理。
- disabled/revoked/expired 三类状态在 UI 和 API 返回中可区分。
- 操作日志记录创建、吊销、轮换。

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
    user_id: str,
    key_id: str,
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

#### Task 1.4: 上游渠道密钥加密

**实现：**
- `secret_crypto.py` 封装 `encrypt_secret()` / `decrypt_secret()` / `mask_secret()`。
- `SECRET_ENCRYPTION_KEY` 从环境变量读取。
- `ChannelForm` 只展示掩码，不回填明文。
- 后端更新渠道时，空值表示不修改原 Key；新值表示重新加密保存。

**验收：**
- 数据库中新保存的渠道 Key 不再明文可读。
- 旧明文渠道仍能调用，编辑保存后转为密文。
- 列表和详情接口不返回完整上游 Key。
- 测试覆盖明文兼容、密文解密、掩码输出、错误密钥处理。

#### Task 1.5: 错误调用自动冻结

**实现：**
- 记录 API Key 级连续认证失败、额度失败、限流失败、上游 4xx 失败。
- 短时间错误超过阈值时自动 disabled 或进入 cooldown。
- 第一版只冻结明显异常，例如 1 分钟内 50 次认证失败或 IP 不匹配。

**验收：**
- 异常 Key 自动冻结。
- 冻结产生通知给管理员和 Key 所属用户。
- 管理后台可看到冻结原因。

### 阶段验收

- API Key IP 白名单、过期、吊销、轮换、限流都有后端测试。
- 渠道密钥新写入为密文，接口不泄露明文。
- 代理中间件对安全策略的返回码清晰：401 未认证，403 无权限/IP 不匹配，429 限流。
- 旧数据有兼容路径和迁移说明。

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

#### Task 2.5: 报表导出

**实现：**
- 新增后端导出接口，支持 CSV。
- 支持筛选：日期范围、部门、项目、用户、模型、渠道。
- 前端后台增加导出按钮。

**验收：**
- 导出的总 token、总成本与页面统计一致。
- 大范围导出有分页或流式策略，不一次性把全部数据加载到内存。

### 阶段验收

- 新请求可按部门/项目归因。
- 并发请求不会透支额度。
- 成本统计不再只停留在 token 层面，有 USD 成本闭环。
- 至少有每日对账报告和 CSV 导出。

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

### 阶段验收

- 管理员可以用 `request_id` 定位一次调用的完整路由过程。
- 渠道健康状态不再只靠列表字段，具备时间窗口指标。
- 熔断/cooldown 可见、可恢复、可审计。

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

### 阶段验收

- 用户能自助提交申请。
- 管理员能审批并自动生效。
- 所有审批动作有通知和审计。

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

### 阶段验收

- 平台支持主要 AI 接口类型。
- 用户身份和权限能对接企业体系。
- 数据安全和运维恢复有明确策略。

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

