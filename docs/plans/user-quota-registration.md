# Plan: 新用户注册额度控制与管理员通知

## Context

**背景**：企业内部 Token Manager 系统，用户通过 API 调用 AI 模型，按 token 用量计费。
当前新用户注册时 `quota=0`，额度扣减逻辑报错信息笼统（统一"用户额度不足"），
且管理员无法及时得知有新用户注册需要分配权限和额度。

**目标**：
1. 新注册用户自动分配默认额度（配置化，默认 0）
2. 新用户注册后即时通知所有管理员（WebSocket + 持久化）
3. 额度相关报错精确化，区分"额度为 0"、"额度不足"、"日限额超"、"月限额超"

**项目现状**：
- 用户模型：`User.quota`（总额度）、`User.quota_used`（已用），默认 0
- 自助注册：`/register` → `quota` 未设置（走 DB default=0），不通知任何人
- 管理员创建：`/admin/users` → 可指定 quota，默认 0
- 额度检查：`ProxyService.check_quota()` 统一返回"用户额度不足"
- 通知系统：已有 `Notification` 模型 + `create_notification()` + WebSocket broadcast，NotificationType 枚举已定义
- `ws_manager.broadcast()` 和 `ws_manager.send_to_user()` 均已就绪

## Global Constraints

- **GC-1**：不改现有 API 响应结构，不破坏现有功能
- **GC-2**：新通知类型 `user_registered` 加入 `NotificationType` 枚举
- **GC-3**：报错 message 对用户友好，不暴露系统内部结构
- **GC-4**：WebSocket 通知失败不影响注册主流程（通知是附加功能）
- **GC-5**：配置项 `DEFAULT_NEW_USER_QUOTA` 通过 `config.py` / `.env` 管理
- **GC-6**：不引入新依赖

## Design Rules

```
R1. 新注册用户 quota = settings.DEFAULT_NEW_USER_QUOTA（默认 0，企业内可按需配置）
R2. 注册成功后，查询所有 role=admin 的用户，向其发送 user_registered 通知
R3. check_quota() 区分四种情况：quota_zero / quota_insufficient / daily_limit_exceeded / monthly_limit_exceeded
R4. 管理员通知内容包含新用户名、邮箱、注册时间
R5. 前端收到 new_notification 类型消息时展示桌面通知（已由现有 WebSocket 处理，无需改动前端）
```

## Tasks

### Task 1: 新增配置项和通知类型

**Files touched**：
- `backend/app/core/config.py` — 新增 `DEFAULT_NEW_USER_QUOTA: int = 0`
- `backend/app/models/notification.py` — `NotificationType` 枚举新增 `user_registered = "user_registered"`

**Acceptance**：
- `.env` 中可配置 `DEFAULT_NEW_USER_QUOTA`，未配置时默认为 0
- `NotificationType.user_registered` 可被正常导入和使用
- 无现有功能被破坏

---

### Task 2: 实现管理员通知函数

**Files touched**：
- `backend/app/services/notification_service.py` — 新增 `notify_admins_new_user(db, user)` 函数

**Acceptance**：
- 函数查询所有 `role == UserRole.admin` 的用户
- 对每个管理员调用 `create_notification()`，类型为 `user_registered`
- 通知 title = "新用户注册"，content 包含用户名和邮箱
- metadata 包含 `user_id` 和 `username` 供前端跳转使用
- 通知发送失败不影响调用方（try/except 包装）
- 单元测试覆盖：正常情况发送 N 条通知；无管理员时发送 0 条；通知失败不抛异常

---

### Task 3: 修改注册接口 — 设默认额度 + 通知管理员

**Files touched**：
- `backend/app/api/v1/auth.py` — `register()` 函数

**Acceptance**：
- 新用户 `quota = settings.DEFAULT_NEW_USER_QUOTA`（注册时设置，不走 DB default）
- 注册成功后调用 `notify_admins_new_user(db, user)`（异步）
- 注册接口原有逻辑（用户名唯一性、邮箱唯一性、默认模型分组）不受影响
- 响应结构不变（`UserInfo`）

---

### Task 4: 优化 check_quota 报错信息

**Files touched**：
- `backend/app/services/proxy_service.py` — `check_quota()` 方法

**Acceptance**：
- `user.quota == 0` 时返回 `reason = "quota_zero"`，`message = "您的账户额度为 0，请联系管理员分配额度后再试。"`
- `quota_remain < estimated` 但 `quota > 0` 时返回 `reason = "quota_insufficient"`，`message = f"额度不足，当前剩余 {quota_remain} tokens，请联系管理员充值。"`
- 日限额超返回 `reason = "daily_limit_exceeded"`，`message = "今日用量已达上限（{日限} tokens），请明日再试。"`（日限从 api_key.daily_limit 读取）
- 月限额超返回 `reason = "monthly_limit_exceeded"`，`message = "本月用量已达上限（{月限} tokens）。"`
- 无现有功能被破坏（其他返回字段结构不变）
- 单元测试覆盖：四种情况的返回值和 message 内容

---

### Task 5: 端到端测试验证

**Files touched**：
- 新增 `backend/tests/test_quota_notification.py`

**Acceptance**：
- 注册新用户 → 查询通知表，确认 admin 收到 user_registered 通知
- quota=0 用户调用 API → 确认收到 "额度为 0" 错误
- quota 不足用户调用 API → 确认收到 "额度不足" 错误（含剩余数量）
- 日限额超用户调用 API → 确认收到 "日限额" 错误
- 月限额超用户调用 API → 确认收到 "月限额" 错误
- 无管理员时注册不报错
- 所有现有测试通过

## Out of Scope

- 前端 UI 改动（WebSocket 推送桌面通知已由现有代码处理）
- 邮件通知（需 SMTP 配置，已知暂无）
- 邀请码、审批流等高级额度控制
- 管理员手动触发通知重发
- 通知的已读/删除等管理功能（已有）
