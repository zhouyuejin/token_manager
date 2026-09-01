"""
Token中转平台 - 主应用入口
"""
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

# 创建FastAPI应用
app = FastAPI(
    title="Token中转平台 API",
    description="API代理/网关服务",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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


@app.on_event("startup")
async def startup_event():
    """启动事件"""
    logger.info("Token中转平台启动")
    
    # 启动定时任务
    try:
        from app.services.scheduler_service import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"定时任务启动失败: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    logger.info("Token中转平台关闭")
    
    # 停止定时任务
    try:
        from app.services.scheduler_service import stop_scheduler
        stop_scheduler()
    except Exception as e:
        logger.warning(f"定时任务停止失败: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
