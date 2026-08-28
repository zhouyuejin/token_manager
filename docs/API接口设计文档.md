# Token中转平台 API接口设计文档

**版本**：v1.0  
**日期**：2026-08-28

---

## 1. 概述

### 1.1 Base URL

| 环境 | Base URL |
|------|----------|
| 开发环境 | `http://localhost:8000` |
| 生产环境 | `https://api.your-domain.com` |

### 1.2 认证方式

除公开接口外，所有接口需要在请求头中携带API Key：

```
Authorization: Bearer <your_api_key>
```

### 1.3 通用响应格式

#### 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

#### 错误响应

```json
{
  "code": 1001,
  "message": "错误描述",
  "detail": "详细错误信息"
}
```

### 1.4 错误码定义

| 错误码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1001 | 参数错误 |
| 1002 | 认证失败 |
| 1003 | 权限不足 |
| 1004 | 资源不存在 |
| 1005 | 额度不足 |
| 1006 | 限流触发 |
| 1007 | 上游服务错误 |
| 1008 | 供应商不可用 |

---

## 2. 认证接口

### 2.1 用户注册

**POST** `/api/v1/auth/register`

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名（4-20位字母数字） |
| password | string | 是 | 密码（8-32位） |
| email | string | 是 | 邮箱 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "usr_abc123",
    "username": "developer01",
    "email": "dev@example.com",
    "created_at": "2026-08-28T10:00:00Z"
  }
}
```

---

### 2.2 用户登录

**POST** `/api/v1/auth/login`

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "user_id": "usr_abc123",
      "username": "developer01",
      "role": "user"
    }
  }
}
```

> 注意：此token用于Web端管理页面登录鉴权，调用中转API需使用API Key

---

### 2.3 修改密码

**POST** `/api/v1/auth/password`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| old_password | string | 是 | 原密码 |
| new_password | string | 是 | 新密码（8-32位） |

---

### 2.4 登出

**POST** `/api/v1/auth/logout`

#### 请求头

```
Authorization: Bearer <login_token>
```

---

## 3. 用户管理接口

### 3.1 获取当前用户信息

**GET** `/api/v1/users/me`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "user_id": "usr_abc123",
    "username": "developer01",
    "email": "dev@example.com",
    "role": "user",
    "quota": 1000000,
    "quota_used": 250000,
    "quota_remain": 750000,
    "created_at": "2026-08-01T00:00:00Z"
  }
}
```

---

### 3.2 用户列表（管理员）

**GET** `/api/v1/admin/users`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### Query参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码，默认1 |
| page_size | int | 否 | 每页数量，默认20 |
| keyword | string | 否 | 用户名/邮箱搜索 |
| role | string | 否 | 角色筛选（admin/user） |
| status | string | 否 | 状态筛选（active/disabled） |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "total": 50,
    "page": 1,
    "page_size": 20,
    "items": [
      {
        "user_id": "usr_abc123",
        "username": "developer01",
        "email": "dev@example.com",
        "role": "user",
        "status": "active",
        "quota": 1000000,
        "quota_used": 250000,
        "created_at": "2026-08-01T00:00:00Z"
      }
    ]
  }
}
```

---

### 3.3 创建用户（管理员）

**POST** `/api/v1/admin/users`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名 |
| password | string | 是 | 初始密码 |
| email | string | 是 | 邮箱 |
| role | string | 否 | 角色（user/admin），默认user |
| quota | int | 否 | 初始额度 |

---

### 3.4 修改用户（管理员）

**PUT** `/api/v1/admin/users/{user_id}`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| quota | int | 否 | 调整额度（正数为增加，负数为减少） |
| status | string | 否 | 状态（active/disabled） |
| role | string | 否 | 角色（user/admin） |

---

### 3.5 删除用户（管理员）

**DELETE** `/api/v1/admin/users/{user_id}`

---

### 3.6 重置用户密码（管理员）

**POST** `/api/v1/admin/users/{user_id}/reset-password`

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| new_password | string | 是 | 新密码 |

---

## 4. API Key管理接口

### 4.1 创建API Key

**POST** `/api/v1/api-keys`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | Key名称 |
| daily_limit | int | 否 | 单日额度限制 |
| monthly_limit | int | 否 | 单月额度限制 |
| ip_whitelist | array | 否 | IP白名单 |
| qps_limit | int | 否 | QPS限制，默认10 |

#### 响应示例

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "api_key": "tmk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "name": "开发环境",
    "key_id": "key_abc123",
    "daily_limit": 100000,
    "monthly_limit": 3000000,
    "qps_limit": 10,
    "ip_whitelist": [],
    "created_at": "2026-08-28T10:00:00Z",
    "last_used_at": null
  }
}
```

> ⚠️ **注意**：api_key只在此刻返回一次，请妥善保存，后续无法查看

---

### 4.2 获取API Key列表

**GET** `/api/v1/api-keys`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "key_id": "key_abc123",
        "name": "开发环境",
        "prefix": "tmk_",
        "daily_limit": 100000,
        "daily_used": 25000,
        "monthly_limit": 3000000,
        "monthly_used": 250000,
        "qps_limit": 10,
        "ip_whitelist": ["10.0.0.0/8"],
        "status": "active",
        "created_at": "2026-08-01T00:00:00Z",
        "last_used_at": "2026-08-28T09:30:00Z"
      }
    ]
  }
}
```

---

### 4.3 更新API Key

**PUT** `/api/v1/api-keys/{key_id}`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | Key名称 |
| daily_limit | int | 否 | 单日额度限制 |
| monthly_limit | int | 否 | 单月额度限制 |
| ip_whitelist | array | 否 | IP白名单 |
| qps_limit | int | 否 | QPS限制 |
| status | string | 否 | 状态（active/disabled） |

---

### 4.4 删除API Key

**DELETE** `/api/v1/api-keys/{key_id}`

---

## 5. 额度管理接口

### 5.1 额度变动记录

**GET** `/api/v1/quota/records`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### Query参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |
| type | string | 否 | 类型（increase/decrease） |
| start_date | string | 否 | 开始日期 |
| end_date | string | 否 | 结束日期 |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "record_id": "qr_abc123",
        "type": "decrease",
        "amount": 1500,
        "balance_before": 100000,
        "balance_after": 98500,
        "source": "api_call",
        "model": "gpt-4",
        "key_name": "开发环境",
        "created_at": "2026-08-28T10:00:00Z"
      }
    ]
  }
}
```

---

### 5.2 管理员调整用户额度

**POST** `/api/v1/admin/users/{user_id}/quota`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| amount | int | 是 | 调整额度（正数为增加，负数为减少） |
| reason | string | 是 | 调整原因 |

---

## 6. 供应商管理接口（管理员）

### 6.1 供应商列表

**GET** `/api/v1/admin/providers`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "provider_id": "prov_openai",
        "name": "OpenAI",
        "type": "openai",
        "endpoint": "https://api.openai.com/v1",
        "api_key": "sk-***",
        "status": "active",
        "priority": 1,
        "timeout": 60,
        "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
        "health_status": "healthy",
        "last_check_at": "2026-08-28T10:00:00Z"
      }
    ]
  }
}
```

---

### 6.2 创建供应商

**POST** `/api/v1/admin/providers`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 供应商名称 |
| type | string | 是 | 类型（openai/anthropic/google/azure） |
| endpoint | string | 是 | API端点 |
| api_key | string | 是 | API密钥 |
| priority | int | 否 | 优先级（数字越小越优先） |
| timeout | int | 否 | 超时时间（秒），默认60 |
| models | array | 否 | 支持的模型列表 |

---

### 6.3 更新供应商

**PUT** `/api/v1/admin/providers/{provider_id}`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 否 | 供应商名称 |
| endpoint | string | 否 | API端点 |
| api_key | string | 否 | API密钥（留空则不更新） |
| priority | int | 否 | 优先级 |
| timeout | int | 否 | 超时时间 |
| models | array | 否 | 支持的模型列表 |
| status | string | 否 | 状态（active/disabled） |

---

### 6.4 删除供应商

**DELETE** `/api/v1/admin/providers/{provider_id}`

---

### 6.5 供应商健康检查

**GET** `/api/v1/admin/providers/{provider_id}/health`

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "provider_id": "prov_openai",
    "status": "healthy",
    "latency_ms": 150,
    "last_check_at": "2026-08-28T10:00:00Z",
    "success_rate": 99.8
  }
}
```

---

### 6.6 模型映射配置

**GET/PUT** `/api/v1/admin/models`

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "model_id": "gpt-4",
        "display_name": "GPT-4",
        "provider_id": "prov_openai",
        "provider_model": "gpt-4",
        "aliases": ["gpt4", "gpt-4-0613"],
        "status": "active"
      },
      {
        "model_id": "claude-3-opus",
        "display_name": "Claude 3 Opus",
        "provider_id": "prov_anthropic",
        "provider_model": "claude-3-opus-20240229",
        "aliases": ["claude-opus", "opus"],
        "status": "active"
      }
    ]
  }
}
```

---

## 7. 中转代理接口

### 7.1 调用大模型API

**POST** `/api/v1/proxy/chat/completions`

#### 请求头

```
Authorization: Bearer <api_key>
Content-Type: application/json
```

> ⚠️ 注意：使用API Key认证，不是登录Token

#### 请求体（兼容OpenAI格式）

```json
{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "你是一个有帮助的助手"},
    {"role": "user", "content": "你好，请介绍一下自己"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

#### 响应（非流式）

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1699000000,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！我是..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 50,
    "completion_tokens": 150,
    "total_tokens": 200
  },
  "extra": {
    "provider": "prov_openai",
    "latency_ms": 1200
  }
}
```

#### 响应（流式）

```
data: {"id":"chatcmpl-xxx","choices":[{"delta":{"role":"assistant","content":"你"},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"好"},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"！"},"index":0}]}

data: {"id":"chatcmpl-xxx","choices":[{"delta":{},"index":0,"finish_reason":"stop"}]}

data: [DONE]
```

---

### 7.2 模型列表

**GET** `/api/v1/proxy/models`

#### 请求头

```
Authorization: Bearer <api_key>
```

#### 响应示例

```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-4",
      "object": "model",
      "created": 1687882411,
      "owned_by": "openai",
      "permission": [],
      "root": "gpt-4",
      "parent": null
    }
  ]
}
```

---

### 7.3 获取余额

**GET** `/api/v1/proxy/balance`

#### 请求头

```
Authorization: Bearer <api_key>
```

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "balance": 750000,
    "daily_limit": 100000,
    "daily_used": 25000,
    "daily_remain": 75000,
    "monthly_limit": 3000000,
    "monthly_used": 250000,
    "monthly_remain": 2750000
  }
}
```

---

## 6.7 供应商配额管理接口（管理员）

### 6.7.1 获取供应商配额

**GET** `/api/v1/admin/providers/{provider_id}/quota`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "provider_id": "prov_volcengine",
    "provider_name": "火山方舟",
    "hourly": {
      "limit": 5000000,
      "used": 2500000,
      "remain": 2500000,
      "percent": 50.00,
      "reset_at": "2026-08-28T15:00:00Z",
      "last_sync": "2026-08-28T10:30:00Z"
    },
    "weekly": {
      "limit": 20000000,
      "used": 8000000,
      "remain": 12000000,
      "percent": 40.00,
      "reset_at": "2026-09-01T00:00:00Z",
      "last_sync": "2026-08-28T10:30:00Z"
    }
  }
}
```

### 6.7.2 手动触发配额同步

**POST** `/api/v1/admin/providers/{provider_id}/quota/sync`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 响应示例

```json
{
  "code": 0,
  "message": "同步成功",
  "data": {
    "hourly": {"used": 2500000, "status": "success"},
    "weekly": {"used": 8000000, "status": "success"},
    "synced_at": "2026-08-28T10:30:00Z"
  }
}
```

### 6.7.3 获取所有供应商配额概览

**GET** `/api/v1/admin/providers/quotas`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "provider_id": "prov_volcengine",
        "provider_name": "火山方舟",
        "hourly": {"used": 2500000, "percent": 50},
        "weekly": {"used": 8000000, "percent": 40},
        "status": "healthy",
        "last_sync": "2026-08-28T10:30:00Z"
      }
    ]
  }
}
```

### 6.7.4 更新供应商配额配置

**PUT** `/api/v1/admin/providers/{provider_id}/quota`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 请求体

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| quota_hourly | int | 否 | 5小时额度（0表示不限） |
| quota_weekly | int | 否 | 周额度（0表示不限） |
| sync_enabled | bool | 否 | 是否启用自动同步 |
| sync_interval | int | 否 | 同步间隔（秒） |

## 8. 用量统计接口

### 8.1 个人用量统计

**GET** `/api/v1/stats/usage`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### Query参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start_date | string | 是 | 开始日期（YYYY-MM-DD） |
| end_date | string | 是 | 结束日期（YYYY-MM-DD） |
| group_by | string | 否 | 分组维度（day/model/api_key） |
| model | string | 否 | 模型筛选 |
| api_key | string | 否 | API Key筛选 |

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "total_tokens": 1250000,
    "total_requests": 3500,
    "avg_latency_ms": 1500,
    "success_rate": 99.5,
    "by_model": [
      {
        "model": "gpt-4",
        "tokens": 800000,
        "requests": 1500,
        "cost": 40.0
      },
      {
        "model": "gpt-3.5-turbo",
        "tokens": 450000,
        "requests": 2000,
        "cost": 2.25
      }
    ],
    "by_day": [
      {
        "date": "2026-08-28",
        "tokens": 150000,
        "requests": 450
      }
    ]
  }
}
```

---

### 8.2 全局用量统计（管理员）

**GET** `/api/v1/admin/stats/usage`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### Query参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| start_date | string | 是 | 开始日期 |
| end_date | string | 是 | 结束日期 |
| group_by | string | 否 | 分组维度（day/user/model/provider） |
| user_id | string | 否 | 用户筛选 |
| provider_id | string | 否 | 供应商筛选 |

---

### 8.3 成本分析（管理员）

**GET** `/api/v1/admin/stats/cost`

#### 请求头

```
Authorization: Bearer <login_token>
```

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "total_cost": 1250.50,
    "by_provider": [
      {
        "provider": "OpenAI",
        "cost": 800.00,
        "percentage": 64
      },
      {
        "provider": "Anthropic",
        "cost": 450.50,
        "percentage": 36
      }
    ],
    "by_model": [
      {
        "model": "gpt-4",
        "cost": 750.00
      },
      {
        "model": "claude-3-opus",
        "cost": 400.00
      }
    ],
    "trend": [
      {"date": "2026-08-21", "cost": 280.00},
      {"date": "2026-08-22", "cost": 310.00}
    ]
  }
}
```

---

## 9. 健康检查接口

### 9.1 系统健康状态

**GET** `/api/v1/health`

#### 响应示例

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "services": {
    "mysql": "healthy",
    "redis": "healthy"
  }
}
```

---

### 9.2 供应商健康状态

**GET** `/api/v1/admin/health/providers`

#### 响应示例

```json
{
  "code": 0,
  "data": {
    "providers": [
      {
        "provider_id": "prov_openai",
        "name": "OpenAI",
        "status": "healthy",
        "latency_ms": 150,
        "success_rate": 99.8,
        "last_check_at": "2026-08-28T10:00:00Z"
      },
      {
        "provider_id": "prov_anthropic",
        "name": "Anthropic",
        "status": "degraded",
        "latency_ms": 3500,
        "success_rate": 95.2,
        "last_check_at": "2026-08-28T10:00:00Z"
      }
    ]
  }
}
```

---

## 10. 附录

### 10.1 API Key使用示例

#### cURL

```bash
# 登录获取Token
curl -X POST https://api.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"developer01","password":"your_password"}'

# 创建API Key
curl -X POST https://api.example.com/api/v1/api-keys \
  -H "Authorization: Bearer <login_token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"生产环境"}'

# 调用中转API
curl -X POST https://api.example.com/api/v1/proxy/chat/completions \
  -H "Authorization: Bearer tmk_xxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

#### Python

```python
import requests

# 调用中转API
url = "https://api.example.com/api/v1/proxy/chat/completions"
headers = {
    "Authorization": "Bearer tmk_xxxxxxxxxxxxxxxxxxxxx",
    "Content-Type": "application/json"
}
data = {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "你好"}],
    "temperature": 0.7
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

#### JavaScript

```javascript
const response = await fetch('https://api.example.com/api/v1/proxy/chat/completions', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer tmk_xxxxxxxxxxxxxxxxxxxxx',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    model: 'gpt-4',
    messages: [{ role: 'user', content: '你好' }]
  })
});

const data = await response.json();
console.log(data);
```

---

### 10.2 限流响应

当触发限流时，返回HTTP 429：

```json
{
  "code": 1006,
  "message": "Rate limit exceeded",
  "detail": "QPS limit: 10, please retry after 100ms",
  "retry_after_ms": 100
}
```

---

### 10.3 额度不足响应

当额度不足时，返回HTTP 402：

```json
{
  "code": 1005,
  "message": "Insufficient quota",
  "detail": "Daily limit: 100000, used: 100000",
  "quota_type": "daily"
}
```

---

*文档版本：v1.0*
