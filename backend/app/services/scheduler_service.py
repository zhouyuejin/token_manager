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

# 存储每个渠道的同步任务ID
_channel_jobs = {}

# 记录上次发送额度不足通知的用户（避免重复发送）
_quota_low_notified_users = set()


async def sync_single_channel(channel_id: str):
    """同步单个渠道的配额"""
    logger.info(f"[Scheduler] 开始同步渠道 {channel_id} 的配额")
    db = SessionLocal()
    try:
        from app.models.channel import Channel, ChannelStatus
        
        channel = db.query(Channel).filter(Channel.channel_id == channel_id).first()
        
        if not channel:
            logger.warning(f"渠道 {channel_id} 不存在")
            return
        
        if channel.status != ChannelStatus.active:
            logger.warning(f"渠道 {channel.name} 状态不是 active，当前状态: {channel.status}")
            return
        
        if not channel.sync_enabled:
            logger.warning(f"渠道 {channel.name} 未启用自动同步 (sync_enabled={channel.sync_enabled})")
            return
        
        logger.info(f"[Scheduler] 渠道 {channel.name} 检查通过，开始同步")
        
        sync_service = create_sync_service(db)
        success = await sync_service.sync_channel_quota(channel)
        
        if success:
            channel.last_sync_at = datetime.now()
            db.commit()
            logger.info(f"渠道 {channel.name} 配额同步成功")
        else:
            logger.warning(f"渠道 {channel.name} 配额同步失败")
    except Exception as e:
        logger.error(f"同步渠道 {channel_id} 配额时出错: {e}")
    finally:
        db.close()


async def sync_all_channels():
    """同步所有启用了自动同步的渠道配额"""
    logger.info("开始同步所有启用了自动同步的渠道配额...")
    
    db = SessionLocal()
    try:
        from app.models.channel import Channel
        
        channels = db.query(Channel).filter(
            Channel.status == "active",
            Channel.sync_enabled == True
        ).all()
        
        for channel in channels:
            job_id = f"sync_channel_{channel.channel_id}"
            interval_seconds = channel.sync_interval or 300
            interval_minutes = interval_seconds // 60
            
            if job_id not in _channel_jobs:
                scheduler.add_job(
                    sync_single_channel,
                    trigger=IntervalTrigger(minutes=interval_minutes),
                    id=job_id,
                    name=f"同步渠道配额-{channel.name}",
                    replace_existing=True,
                    kwargs={"channel_id": channel.channel_id}
                )
                _channel_jobs[job_id] = channel.channel_id
                logger.info(f"为渠道 {channel.name} 创建同步任务，间隔 {interval_minutes} 分钟")
        
        active_channel_ids = {c.channel_id for c in channels}
        for job_id, ch_id in list(_channel_jobs.items()):
            if ch_id not in active_channel_ids:
                try:
                    scheduler.remove_job(job_id)
                    del _channel_jobs[job_id]
                    logger.info(f"已移除渠道 {ch_id} 的同步任务")
                except Exception:
                    pass
        
        logger.info(f"同步任务调度完成，共 {len(_channel_jobs)} 个任务")
    except Exception as e:
        logger.error(f"同步所有渠道配额失败: {e}")
    finally:
        db.close()


async def sync_channel_quotas():
    """同步所有渠道配额"""
    logger.info("开始同步渠道配额...")
    
    db = SessionLocal()
    try:
        sync_service = create_sync_service(db)
        result = await sync_service.sync_all_channels()
        logger.info(f"渠道配额同步完成: {result}")
    except Exception as e:
        logger.error(f"同步渠道配额失败: {e}")
    finally:
        db.close()


def update_channel_sync_job(channel_id: str, channel_name: str, sync_enabled: bool, sync_interval: int):
    """更新渠道的同步任务"""
    job_id = f"sync_channel_{channel_id}"
    interval_minutes = max(1, sync_interval // 60)
    
    logger.info(f"[Scheduler] 更新渠道 {channel_name} 同步任务: enabled={sync_enabled}, interval={sync_interval}秒")
    
    if sync_enabled:
        scheduler.add_job(
            sync_single_channel,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=job_id,
            name=f"同步渠道配额-{channel_name}",
            replace_existing=True,
            kwargs={"channel_id": channel_id}
        )
        _channel_jobs[job_id] = channel_id
    else:
        try:
            scheduler.remove_job(job_id)
            if job_id in _channel_jobs:
                del _channel_jobs[job_id]
        except Exception:
            pass


def remove_channel_sync_job(channel_id: str):
    """移除渠道的同步任务"""
    job_id = f"sync_channel_{channel_id}"
    try:
        scheduler.remove_job(job_id)
        if job_id in _channel_jobs:
            del _channel_jobs[job_id]
    except Exception:
        pass


def check_quota_low_alert():
    """检查额度不足并发送通知"""
    logger.info("开始检查额度不足用户...")
    
    global _quota_low_notified_users
    
    db = SessionLocal()
    try:
        from app.models.user import User, UserStatus
        
        users = db.query(User).filter(
            User.quota_low_alert == True,
            User.status == UserStatus.active
        ).all()
        
        notified_count = 0
        for user in users:
            if user.quota <= 0:
                continue
                
            percent_remaining = ((user.quota - user.quota_used) / user.quota) * 100
            
            if percent_remaining < 20:
                user_key = f"{user.user_id}_{date.today()}"
                
                if user_key not in _quota_low_notified_users:
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
        
        users = db.query(User).filter(
            User.daily_report == True,
            User.status == UserStatus.active
        ).all()
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        sent_count = 0
        for user in users:
            daily_usage = db.query(QuotaRecord).filter(
                QuotaRecord.user_id == user.user_id,
                QuotaRecord.created_at >= today_start
            ).all()
            
            daily_used = sum(record.amount for record in daily_usage)
            
            model_usage = {}
            for record in daily_usage:
                model_name = record.model_name or "Unknown"
                model_usage[model_name] = model_usage.get(model_name, 0) + record.amount
            
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
        
        logger.info(f"每日报表发送完成，共发送 {sent_count} 份")
    except Exception as e:
        logger.error(f"发送每日报表失败: {e}")
    finally:
        db.close()


def setup_scheduler():
    """设置定时任务"""
    scheduler.add_job(
        sync_all_channels,
        trigger=IntervalTrigger(minutes=5),
        id="sync_all_channels",
        name="管理渠道同步任务",
        replace_existing=True
    )
    
    scheduler.add_job(
        check_quota_low_alert,
        trigger=CronTrigger(minute=0),
        id="check_quota_low_alert",
        name="检查额度不足",
        replace_existing=True
    )
    
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
    
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(sync_all_channels())
        else:
            loop.run_until_complete(sync_all_channels())
    except Exception as e:
        logger.warning(f"启动时同步渠道任务失败: {e}")
    
    logger.info("定时任务已启动")


def stop_scheduler():
    """停止定时任务"""
    scheduler.shutdown()
    logger.info("定时任务已停止")


async def notify_quota_change(
    user_id: str,
    change_amount: int,
    change_type: str,
    reason: str = ""
):
    """发送额度变动通知"""
    db = SessionLocal()
    try:
        from app.models.user import User, UserStatus
        
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            return False
        
        if not user.quota_change_alert or user.status != UserStatus.active:
            return False
        
        await send_quota_change_notification(
            to_email=user.email,
            username=user.username,
            change_amount=change_amount,
            change_type=change_type,
            current_quota=user.quota,
            reason=reason
        )
        
        return True
    except Exception as e:
        logger.error(f"发送额度变动通知失败: {e}")
        return False
    finally:
        db.close()
