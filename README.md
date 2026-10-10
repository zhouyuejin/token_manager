# Token中转平台

API代理/网关服务，为公司内部提供统一访问大模型API的能力。

## 功能特性

- 统一API入口，支持多供应商（OpenAI、Anthropic、Moonshot、火山方舟等）
- API Key管理，按Key限流
- 用量统计与配额管理
- 供应商配额同步（5小时用量、周用量）
- 故障转移与熔断机制
- 模型分组（每组关联若干供应商及其模型）；可标记分组为“默认”，用户访问模型时取“默认分组 ∪ 用户授权分组”的并集

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI (Python 3.10+) |
| 数据库 | MySQL 8.0 |
| 缓存 | Redis 7.0 |
| 网关 | Nginx |
| 监控 | Prometheus + Grafana |
| 部署 | Docker + Docker Compose |

## 用户使用手册

普通用户操作、API 接入与管理员配置见[用户使用手册](docs/用户使用手册.md)。

当前功能实现状态、支持边界和待验收项统一见[当前能力表](docs/当前能力表.md)。旧实施计划保留需求和历史记录。

## 快速开始

阿里云 ECS 镜像部署步骤见[ACR 部署操作手册](docs/阿里云ACR部署.md)。

## 网页 AI 对话

1. 管理员在“用户管理”中为员工分配所属部门（管理员自身也需要分配）。
2. 配置用户可用模型分组及额度，确保所属部门已启用且预算充足。
3. 员工登录后选择可用模型并发送消息，无需项目授权或 API Key。

网页对话仅计入用户和当前所属部门，不绑定项目。部门的“网页对话审计摘要”开关控制用量日志中的脱敏摘要；关闭不影响用户自己的聊天记录保存。员工调整部门后，新请求按新部门计费，已开始请求和历史账目保持原归属。

### 升级部门对话版本

部署前先在后端执行 `alembic upgrade head`（Docker 环境可执行 `docker compose exec backend alembic upgrade head`），再启动新版服务。现有用户的所属部门默认为空，管理员必须明确分配；系统不会从项目推测部门。未分配部门或部门停用时，可以查看历史会话，但不能发送新消息。已有无 Key 网页账目后不能直接降级为 Key 必填结构。

外部程序调用仍须选择已授权项目、申请 API Key 并等待审批，使用方式与网页对话分开。

## 管理员注意

- 必须将至少一个模型分组标记为「默认」(is_default=1 且 status=active)，否则所有用户将被拒绝访问任何模型（启动期会输出 warn 日志，AdminLayout 也会显示黄色横幅）。
- 「设置默认」操作对禁用分组返回 400；请先把目标分组启用。

## 开发

### 本地开发

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# 安装依赖
cd backend
pip install -r requirements.txt

# 启动后端
uvicorn app.main:app --reload
```

### 目录结构

```
token-manager/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/           # API路由
│   │   │   └── v1/       # API v1版本
│   │   ├── core/          # 核心配置
│   │   ├── models/         # 数据模型
│   │   ├── schemas/       # Pydantic模型
│   │   ├── services/       # 业务逻辑
│   │   └── main.py        # 应用入口
│   ├── alembic/           # 数据库迁移
│   ├── tests/             # 测试
│   ├── requirements.txt   # Python依赖
│   └── Dockerfile
│
├── frontend/               # React 管理后台与网页对话
│
├── nginx/                  # Nginx配置
│   ├── nginx.conf
│   └── conf.d/
│
├── deploy/                 # 部署配置
│
├── docker-compose.yml      # Docker编排
├── .env                    # 环境变量
└── README.md
```

## 配置说明

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| MYSQL_HOST | 数据库主机 | mysql |
| MYSQL_PORT | 数据库端口 | 3306 |
| MYSQL_USER | 数据库用户 | token_user |
| MYSQL_PASSWORD | 数据库密码 | token_password |
| MYSQL_DATABASE | 数据库名 | token_db |
| REDIS_HOST | Redis主机 | redis |
| REDIS_PORT | Redis端口 | 6379 |
| REDIS_PASSWORD | Redis密码 | - |
| SECRET_KEY | JWT密钥 | - |
| LOG_LEVEL | 日志级别 | INFO |

### 添加供应商

1. 访问管理后台
2. 进入供应商管理
3. 点击"添加供应商"
4. 填写供应商信息（名称、类型、API Key等）
5. 保存

### 配置用量同步

1. 编辑供应商
2. 开启"启用自动同步"
3. 配置5小时额度/周额度
4. 保存

## API使用

### 获取Token

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin&password=admin123"
```

### 创建API Key

```bash
curl -X POST http://localhost:8000/api/v1/api-keys \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"测试Key","project_id":"<已授权项目ID>"}'
```

### 调用中转API

```bash
curl -X POST http://localhost:8000/api/v1/proxy/chat/completions \
  -H "Authorization: Bearer <api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

## 监控

### Grafana仪表盘

- 访问 http://localhost:3000
- 默认账号: admin/admin123
- 预置仪表盘：API调用量、响应时间、成功率

### Prometheus

- 访问 http://localhost:9090

## 许可证

MIT License
