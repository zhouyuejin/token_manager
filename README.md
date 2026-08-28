# Token中转平台

API代理/网关服务，为公司内部提供统一访问大模型API的能力。

## 功能特性

- 统一API入口，支持多供应商（OpenAI、Anthropic、Moonshot、火山方舟等）
- API Key管理，按Key限流
- 用量统计与配额管理
- 供应商配额同步（5小时用量、周用量）
- 故障转移与熔断机制

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI (Python 3.10+) |
| 数据库 | MySQL 8.0 |
| 缓存 | Redis 7.0 |
| 网关 | Nginx |
| 监控 | Prometheus + Grafana |
| 部署 | Docker + Docker Compose |

## 快速开始

### 前置要求

- Docker Desktop
- Docker Compose

### 1. 克隆项目

```bash
git clone <repository-url>
cd token-manager
```

### 2. 配置环境变量

```bash
# 复制环境变量文件
cp .env.example .env

# 编辑配置（可选）
vim .env
```

### 3. 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
```

### 4. 访问服务

| 服务 | 地址 |
|------|------|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Grafana | http://localhost:3000 |

### 5. 初始化数据

```bash
# 进入后端容器
docker-compose exec backend bash

# 初始化数据库（首次）
python -c "from app.core.database import engine, Base; Base.metadata.create_all(bind=engine)"
```

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
├── frontend/               # 前端（待开发）
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
  -d '{"name":"测试Key"}'
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
