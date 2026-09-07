"""
Token中转平台 - 主应用入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1 import api_router
from app.api.v1.ws import router as ws_router
from app.core.config import settings
from app.core.database import engine, Base
from app.middleware import ProxyAuthMiddleware

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 初始化日志
logger.add(
    "logs/app.log",
    rotation="500 MB",
    retention="10 days",
    level=settings.LOG_LEVEL
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("Token中转平台启动")
    
    # 检查并创建初始管理员用户
    try:
        from app.core.database import SessionLocal
        from app.models.user import User, UserRole, UserStatus
        db = SessionLocal()
        try:
            admin_exists = db.query(User).filter(User.username == "admin").first()
            if not admin_exists:
                # SHA256(FRONTEND_SALT + "admin123")
                admin_password = "f10d777793088354212c24aa082e8c06ed0c048837d1bb87096b04a25dc50eb5"
                admin = User(
                    user_id="usr_admin",
                    username="admin",
                    email="admin@example.com",
                    password=admin_password,
                    role=UserRole.admin,
                    quota=100000000,
                    status=UserStatus.active
                )
                db.add(admin)
                
                # 创建测试用户 (密码: user123)
                test_password = "d51c051c47c4be47d3e9b231a8e04fff39b3c1402b91d732c554e966d3100556"
                test_user = User(
                    user_id="usr_test",
                    username="testuser",
                    email="test@example.com",
                    password=test_password,
                    role=UserRole.user,
                    quota=1000000,
                    status=UserStatus.active
                )
                db.add(test_user)
                db.commit()
                logger.info("初始用户创建成功: admin, testuser")
            else:
                logger.info("管理员用户已存在，跳过创建")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"检查/创建初始用户失败: {e}")
    
    # GC-4(a): Startup warn when no active default model group
    try:
        from app.core.database import SessionLocal
        from app.models.model_group import ModelGroup
        db = SessionLocal()
        try:
            default_count = db.query(ModelGroup).filter(
                ModelGroup.is_default == 1,
                ModelGroup.status == "active"
            ).count()
            if default_count == 0:
                logger.warning(
                    "[Token中转平台] 没有设置默认模型分组(is_default=1 且 status=active)！"
                    "请在管理后台创建并设置默认分组，以免用户无法正常使用API。"
                )
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"检查默认模型分组失败: {e}")
    
    # 启动定时任务
    try:
        from app.tasks.daily_report import init_scheduler
        init_scheduler()
    except Exception as e:
        logger.warning(f"每日报表定时任务启动失败: {e}")
    
    # 启动其他定时任务
    try:
        from app.services.scheduler_service import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"定时任务启动失败: {e}")
    
    yield
    
    # 关闭时
    logger.info("Token中转平台关闭")
    
    # 停止定时任务
    try:
        from app.tasks.daily_report import shutdown_scheduler
        shutdown_scheduler()
    except Exception as e:
        logger.warning(f"每日报表定时任务停止失败: {e}")
    
    try:
        from app.services.scheduler_service import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning(f"定时任务停止失败: {e}")


# 创建FastAPI应用
app = FastAPI(
    title="Token中转平台 API",
    description="API代理/网关服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加代理认证中间件
app.add_middleware(ProxyAuthMiddleware)

# 注册WebSocket路由（不需要 /api/v1 前缀）
app.include_router(ws_router)

# 注册API路由
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
