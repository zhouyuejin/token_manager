"""
定时任务服务
"""
import asyncio
from datetime import date, datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app.core.database import SessionLocal
from app.services.sync_service import create_sync_service
from app.services.email_service import (
    send_quota_low_alert,
    send_daily_report,
    send_quota_change_notification
)


# 全局调度器
scheduler = AsyncIOScheduler()

# 存储每个供应商的同步任务ID
_provider_jobs = {}

# 记录上次发送额度不足通知的用户（避免重复发送）
_quota_low_notified_users = set()


async def sync_single_provider(provider_id: str):
    """同步单个供应商的配额"""
    logger.info(f"[Scheduler] 开始同步供应商 {provider_id} 的配额")
    db = SessionLocal()
    try:
        from app.models.provider import Provider
        from app.models.provider import ProviderStatus
        
        provider = db.query(Provider).filter(
            Provider.provider_id == provider_id
        ).first()
        
        if not provider:
            logger.warning(f"供应商 {provider_id} 不存在")
            return
        
        if provider.status != ProviderStatus.active:
            logger.warning(f"供应商 {provider.name} 状态不是 active，当前状态: {provider.status}")
            return
        
        if provider.sync_enabled != 1:
            logger.warning(f"供应商 {provider.name} 未启用自动同步 (sync_enabled={provider.sync_enabled})")
            return
        
        logger.info(f"[Scheduler] 供应商 {provider.name} 检查通过，开始同步")
        
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
    
    logger.info(f"[Scheduler] 更新供应商 {provider_name} 同步任务: enabled={sync_enabled}, interval={sync_interval}秒 ({interval_minutes}分钟)")
    
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
        logger.info(f"[Scheduler] 已添加供应商 {provider_name} 的同步任务，间隔 {interval_minutes} 分钟")
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
        from datetime import date, datetime
        
        today = date.today()
        
        # 重置所有API Key的日用量
        api_keys = db.query(ApiKey).all()
        for key in api_keys:
            # 确保daily_reset_at是date类型进行比较
            reset_date = key.daily_reset_at.date() if key.daily_reset_at else None
            if reset_date is None or reset_date != today:
                key.daily_used = 0
                key.daily_reset_at = datetime.now()
        
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
        from datetime import date, datetime
        
        today = date.today()
        
        # 重置所有API Key的月用量
        api_keys = db.query(ApiKey).all()
        for key in api_keys:
            # 确保monthly_reset_at是date类型进行比较
            reset_date = key.monthly_reset_at.date() if key.monthly_reset_at else None
            if reset_date is None or reset_date.month != today.month or reset_date.year != today.year:
                key.monthly_used = 0
                key.monthly_reset_at = datetime.now()
        
        db.commit()
        logger.info(f"已重置 {len(api_keys)} 个API Key的月用量")
    except Exception as e:
        logger.error(f"重置每月用量失败: {e}")
    finally:
        db.close()


def check_quota_low_alert():
    """检查额度不足并发送通知"""
    logger.info("开始检查额度不足用户...")
    
    global _quota_low_notified_users
    
    db = SessionLocal()
    try:
        from app.models.user import User, UserStatus
        
        # 查询所有启用了额度不足通知且状态正常的用户
        users = db.query(User).filter(
            User.quota_low_alert == True,
            User.status == UserStatus.active
        ).all()
        
        notified_count = 0
        for user in users:
            if user.quota <= 0:
                continue
                
            percent_remaining = ((user.quota - user.quota_used) / user.quota) * 100
            
            # 当剩余额度低于20%时发送通知
            if percent_remaining < 20:
                user_key = f"{user.user_id}_{date.today()}"
                
                # 如果今天还没有发送过通知
                if user_key not in _quota_low_notified_users:
                    # 异步发送邮件
                    asyncio.create_task(
                        send_quota_low_alert(
                            to_email=user.email,
                            username=user.username,
                            quota=user.quota,
                            quota_used=user.quota_used,
                            threshold_percent=20
                        )
                    )
                    _quota_low_notified_users.add(user_key)
                    notified_count += 1
                    logger.info(f"已向用户 {user.username} 发送额度不足通知")
        
        logger.info(f"额度不足检查完成，共通知 {notified_count} 位用户")
    except Exception as e:
        logger.error(f"检查额度不足失败: {e}")
    finally:
        db.close()


def send_daily_reports():
    """发送每日用量报表"""
    logger.info("开始发送每日用量报表...")
    
    db = SessionLocal()
    try:
        from app.models.user import User, UserStatus
        from app.models.quota_record import QuotaRecord
        from datetime import datetime, timedelta
        
        # 查询所有启用了每日报表的用户
        users = db.query(User).filter(
            User.daily_report == True,
            User.status == UserStatus.active
        ).all()
        
        # 获取今天的开始时间
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        sent_count = 0
        for user in users:
            # 计算今日使用量（从 quota_records 表统计）
            daily_usage = db.query(QuotaRecord).filter(
                QuotaRecord.user_id == user.user_id,
                QuotaRecord.created_at >= today_start
            ).all()
            
            daily_used = sum(record.amount for record in daily_usage)
            
            # 获取模型使用统计
            model_usage = {}
            for record in daily_usage:
                model_name = record.model_name or "Unknown"
                model_usage[model_name] = model_usage.get(model_name, 0) + record.amount
            
            # 异步发送邮件
            asyncio.create_task(
                send_daily_report(
                    to_email=user.email,
                    username=user.username,
                    quota=user.quota,
                    quota_used=user.quota_used,
                    daily_used=daily_used,
                    model_usage=model_usage
                )
            )
            sent_count += 1
            logger.info(f"已向用户 {user.username} 发送每日用量报表")
        
        logger.info(f"每日报表发送完成，共发送 {sent_count} 份")
    except Exception as e:
        logger.error(f"发送每日报表失败: {e}")
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
        trigger=CronTrigger(hour=0, minute=0),
        id="reset_daily_usage",
        name="重置每日用量",
        replace_existing=True
    )
    
    # 每月1号凌晨0点重置每月用量
    scheduler.add_job(
        reset_monthly_usage,
        trigger=CronTrigger(day=1, hour=0, minute=0),
        id="reset_monthly_usage",
        name="重置每月用量",
        replace_existing=True
    )
    
    # 每小时检查一次额度不足
    scheduler.add_job(
        check_quota_low_alert,
        trigger=CronTrigger(minute=0),
        id="check_quota_low_alert",
        name="检查额度不足",
        replace_existing=True
    )
    
    # 每天早上8点发送每日用量报表
    scheduler.add_job(
        send_daily_reports,
        trigger=CronTrigger(hour=8, minute=0),
        id="send_daily_reports",
        name="发送每日用量报表",
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


# === 额度变动通知功能 ===

async def notify_quota_change(
    user_id: str,
    change_amount: int,
    change_type: str,
    reason: str = ""
):
    """
    发送额度变动通知（供外部调用）
    
    Args:
        user_id: 用户ID
        change_amount: 变动额度
        change_type: 变动类型 (increase/decrease)
        reason: 变动原因
    """
    db = SessionLocal()
    try:
        from app.models.user import User, UserStatus
        
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            logger.warning(f"用户 {user_id} 不存在")
            return False
        
        # 检查用户是否启用了额度变动通知
        if not user.quota_change_alert or user.status != UserStatus.active:
            logger.info(f"用户 {user.username} 未启用额度变动通知，跳过")
            return False
        
        await send_quota_change_notification(
            to_email=user.email,
            username=user.username,
            change_amount=change_amount,
            change_type=change_type,
            current_quota=user.quota,
            reason=reason
        )
        
        logger.info(f"已向用户 {user.username} 发送额度变动通知")
        return True
        
    except Exception as e:
        logger.error(f"发送额度变动通知失败: {e}")
        return False
    finally:
        db.close()
