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

# 存储每个供应商的同步任务ID
_provider_jobs = {}


async def sync_single_provider(provider_id: str):
    """同步单个供应商的配额"""
    db = SessionLocal()
    try:
        from app.models.provider import Provider
        
        provider = db.query(Provider).filter(
            Provider.provider_id == provider_id,
            Provider.status == "active",
            Provider.sync_enabled == 1
        ).first()
        
        if not provider:
            logger.warning(f"供应商 {provider_id} 不存在或未启用自动同步")
            return
        
        sync_service = create_sync_service(db)
        success = await sync_service.sync_provider_quota(provider)
        
        if success:
            # 更新最后同步时间
            provider.last_sync_at = datetime.now()
            db.commit()
            logger.info(f"供应商 {provider.name} 配额同步成功")
        else:
            logger.warning(f"供应商 {provider.name} 配额同步失败")
    except Exception as e:
        logger.error(f"同步供应商 {provider_id} 配额时出错: {e}")
    finally:
        db.close()


async def sync_all_providers():
    """同步所有启用了自动同步的供应商配额"""
    logger.info("开始同步所有启用了自动同步的供应商配额...")
    
    db = SessionLocal()
    try:
        from app.models.provider import Provider
        
        providers = db.query(Provider).filter(
            Provider.status == "active",
            Provider.sync_enabled == 1
        ).all()
        
        # 为每个启用了自动同步的供应商创建独立任务
        for provider in providers:
            job_id = f"sync_provider_{provider.provider_id}"
            interval_seconds = provider.sync_interval or 300  # 默认5分钟
            interval_minutes = interval_seconds // 60
            
            if job_id not in _provider_jobs:
                scheduler.add_job(
                    sync_single_provider,
                    trigger=IntervalTrigger(minutes=interval_minutes),
                    id=job_id,
                    name=f"同步供应商配额-{provider.name}",
                    replace_existing=True,
                    kwargs={"provider_id": provider.provider_id}
                )
                _provider_jobs[job_id] = provider.provider_id
                logger.info(f"为供应商 {provider.name} 创建同步任务，间隔 {interval_minutes} 分钟")
        
        # 清理已禁用的供应商任务
        active_provider_ids = {p.provider_id for p in providers}
        for job_id, provider_id in list(_provider_jobs.items()):
            if provider_id not in active_provider_ids:
                try:
                    scheduler.remove_job(job_id)
                    del _provider_jobs[job_id]
                    logger.info(f"已移除供应商 {provider_id} 的同步任务")
                except Exception:
                    pass
        
        logger.info(f"同步任务调度完成，共 {len(_provider_jobs)} 个任务")
    except Exception as e:
        logger.error(f"同步所有供应商配额失败: {e}")
    finally:
        db.close()


async def sync_provider_quotas():
    """同步所有供应商配额（兼容旧接口）"""
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


def update_provider_sync_job(provider_id: str, provider_name: str, sync_enabled: bool, sync_interval: int):
    """更新供应商的同步任务"""
    job_id = f"sync_provider_{provider_id}"
    interval_minutes = max(1, sync_interval // 60)  # 至少1分钟
    
    if sync_enabled:
        # 添加或更新任务
        scheduler.add_job(
            sync_single_provider,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name=f"同步供应商配额-{provider_name}",
            replace_existing=True,
            kwargs={"provider_id": provider_id}
        )
        _provider_jobs[job_id] = provider_id
        logger.info(f"已更新供应商 {provider_name} 的同步任务，间隔 {interval_minutes} 分钟")
    else:
        # 移除任务
        try:
            scheduler.remove_job(job_id)
            if job_id in _provider_jobs:
                del _provider_jobs[job_id]
            logger.info(f"已移除供应商 {provider_name} 的同步任务")
        except Exception:
            pass


def remove_provider_sync_job(provider_id: str):
    """移除供应商的同步任务"""
    job_id = f"sync_provider_{provider_id}"
    try:
        scheduler.remove_job(job_id)
        if job_id in _provider_jobs:
            del _provider_jobs[job_id]
        logger.info(f"已移除供应商 {provider_id} 的同步任务")
    except Exception:
        pass


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
    # 每5分钟检查并更新所有供应商的同步任务
    scheduler.add_job(
        sync_all_providers,
        trigger=IntervalTrigger(minutes=5),
        id="sync_all_providers",
        name="管理供应商同步任务",
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
    
    # 启动后立即同步一次所有供应商的任务
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(sync_all_providers())
        else:
            loop.run_until_complete(sync_all_providers())
    except Exception as e:
        logger.warning(f"启动时同步供应商任务失败: {e}")
    
    logger.info("定时任务已启动")


def stop_scheduler():
    """停止定时任务"""
    scheduler.shutdown()
    logger.info("定时任务已停止")
