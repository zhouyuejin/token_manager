"""
定时任务服务
"""
import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.core.database import SessionLocal
from app.services.sync_service import create_sync_service


# 全局调度器
scheduler = AsyncIOScheduler()


async def sync_provider_quotas():
    """同步所有供应商配额"""
    logger.info("开始同步供应商配额...")
    
    db = SessionLocal()
    try:
        sync_service = create_sync_service(db)
        result = await sync_service.sync_all_providers()
        logger.info(f"供应商配额同步完成: {result}")
    except Exception as e:
        logger.error(f"同步供应商配额失败: {e}")
    finally:
        db.close()


def reset_daily_usage():
    """重置每日用量"""
    logger.info("开始重置每日用量...")
    
    db = SessionLocal()
    try:
        from app.models.api_key import ApiKey
        from datetime import date
        
        today = date.today()
        
        # 重置所有API Key的日用量
        api_keys = db.query(ApiKey).all()
        for key in api_keys:
            if key.daily_reset_at is None or key.daily_reset_at != today:
                key.daily_used = 0
                key.daily_reset_at = today
        
        db.commit()
        logger.info(f"已重置 {len(api_keys)} 个API Key的日用量")
    except Exception as e:
        logger.error(f"重置每日用量失败: {e}")
    finally:
        db.close()


def reset_monthly_usage():
    """重置每月用量"""
    logger.info("开始重置每月用量...")
    
    db = SessionLocal()
    try:
        from app.models.api_key import ApiKey
        from datetime import date
        
        today = date.today()
        
        # 重置所有API Key的月用量
        api_keys = db.query(ApiKey).all()
        for key in api_keys:
            if key.monthly_reset_at is None or key.monthly_reset_at.month != today.month:
                key.monthly_used = 0
                key.monthly_reset_at = today
        
        db.commit()
        logger.info(f"已重置 {len(api_keys)} 个API Key的月用量")
    except Exception as e:
        logger.error(f"重置每月用量失败: {e}")
    finally:
        db.close()


def setup_scheduler():
    """设置定时任务"""
    # 每5分钟同步一次供应商配额
    scheduler.add_job(
        sync_provider_quotas,
        trigger=IntervalTrigger(minutes=5),
        id="sync_provider_quotas",
        name="同步供应商配额",
        replace_existing=True
    )
    
    # 每天凌晨0点重置每日用量
    scheduler.add_job(
        reset_daily_usage,
        trigger="cron",
        hour=0,
        minute=0,
        id="reset_daily_usage",
        name="重置每日用量",
        replace_existing=True
    )
    
    # 每月1号凌晨0点重置每月用量
    scheduler.add_job(
        reset_monthly_usage,
        trigger="cron",
        day=1,
        hour=0,
        minute=0,
        id="reset_monthly_usage",
        name="重置每月用量",
        replace_existing=True
    )
    
    logger.info("定时任务已设置")


def start_scheduler():
    """启动定时任务"""
    setup_scheduler()
    scheduler.start()
    logger.info("定时任务已启动")


def stop_scheduler():
    """停止定时任务"""
    scheduler.shutdown()
    logger.info("定时任务已停止")
