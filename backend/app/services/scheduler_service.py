"""
定时任务服务
"""
import asyncio
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app.core.database import SessionLocal
from app.services.sync_service import create_sync_service
from app.services.email_service import (
    send_quota_change_notification
)
from app.services.metrics import active_channel_cooldowns


# 全局调度器
scheduler = AsyncIOScheduler()

# 存储每个渠道的同步任务ID
_channel_jobs = {}


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


async def check_quota_low_alert():
    """Create one low-quota notification per user per day, including idle users."""
    from app.models.user import User, UserStatus
    from app.models.notification import Notification, NotificationType
    from app.services.notification_service import create_notification
    with SessionLocal() as db:
        users = db.query(User).filter(User.quota_low_alert.is_(True),
                                     User.status == UserStatus.active, User.quota > 0).all()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for user in users:
            remaining = user.quota - user.quota_used
            if remaining / user.quota >= 0.2:
                continue
            if db.query(Notification.id).filter(Notification.user_id == user.user_id,
                    Notification.type == NotificationType.quota_low,
                    Notification.created_at >= today).first():
                continue
            await create_notification(db, user.user_id, NotificationType.quota_low,
                "额度不足提醒", f"您的剩余额度已低于20%，当前剩余 {remaining} tokens，请及时充值。")


def setup_scheduler():
    """设置定时任务"""
    scheduler.add_job(refresh_exchange_rate, trigger=IntervalTrigger(hours=1),
                      id='refresh_exchange_rate', name='更新 USD/CNY 参考汇率', replace_existing=True,
                      next_run_time=datetime.now())
    scheduler.add_job(check_upstream_health, trigger=IntervalTrigger(seconds=60),
                      id='check_upstream_health', name='探测上游渠道', replace_existing=True)
    scheduler.add_job(check_budget_alerts, trigger=IntervalTrigger(seconds=60),
                      id='check_budget_alerts', name='检查预算阈值告警', replace_existing=True)
    scheduler.add_job(check_operational_alerts, trigger=IntervalTrigger(seconds=60),
                      id='check_operational_alerts', name='检查渠道配额和项目异常告警', replace_existing=True)
    scheduler.add_job(
        run_daily_billing_reconcile,
        trigger=CronTrigger(hour=2, minute=15, timezone="Asia/Shanghai"),
        id="daily_billing_reconcile",
        name="每日账务对账",
        replace_existing=True,
    )

    scheduler.add_job(
        expire_quota_reservations,
        trigger=IntervalTrigger(seconds=60),
        id='expire_quota_reservations',
        name='释放过期预扣',
        replace_existing=True,
    )
    scheduler.add_job(
        sync_all_channels,
        trigger=IntervalTrigger(minutes=5),
        id="sync_all_channels",
        name="管理渠道同步任务",
        replace_existing=True
    )
    
    scheduler.add_job(check_quota_low_alert, trigger=CronTrigger(minute=0),
                      id="check_quota_low_alert", name="检查额度不足", replace_existing=True)
    from app.services.email_service import deliver_notification_emails
    scheduler.add_job(
        deliver_notification_emails,
        trigger=IntervalTrigger(seconds=30),
        id="deliver_notification_emails",
        name="发送通知邮件",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("定时任务已设置")


def run_daily_billing_reconcile():
    from zoneinfo import ZoneInfo
    from app.services.billing_reconcile_service import BillingReconcileService
    business_date = datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(days=1)
    with SessionLocal() as db:
        BillingReconcileService(db).run(business_date)


def expire_quota_reservations():
    from app.services.quota_reservation_service import QuotaReservationService
    with SessionLocal() as db:
        QuotaReservationService(db).expire()


async def check_budget_alerts():
    from app.services.budget_service import BudgetService
    with SessionLocal() as db:
        await BudgetService(db).check_alerts()


async def check_operational_alerts():
    from app.services.alert_service import AlertService
    with SessionLocal() as db:
        await AlertService(db).check()


async def check_upstream_health():
    from app.models.channel import Channel, ChannelHealthStatus
    from app.services.channel_test_service import ChannelTestService
    from app.services.secret_crypto import decrypt_secret

    with SessionLocal() as db:
        channels = db.query(Channel).filter(Channel.status == "active").all()
        async def probe(channel):
            try:
                result = await ChannelTestService().test_connection(
                    type_=channel.type.value,
                    endpoint=channel.endpoint,
                    api_key=decrypt_secret(channel.api_key),
                    timeout=min(channel.timeout or 10, 10),
                )
                channel.health_status = (
                    ChannelHealthStatus.healthy if result.get("success")
                    else ChannelHealthStatus.degraded
                )
            except Exception as exc:
                logger.warning("上游渠道探测失败 channel_id=%s error=%s", channel.channel_id, type(exc).__name__)
                channel.health_status = ChannelHealthStatus.degraded
            channel.last_check_at = datetime.utcnow()

        await asyncio.gather(*(probe(channel) for channel in channels))
        db.commit()
        now = datetime.utcnow()
        active = sum(bool(ch.cooldown_until and ch.cooldown_until > now) for ch in channels)
        active_channel_cooldowns.set(active)


def start_scheduler():
    """启动定时任务"""
    setup_scheduler()
    scheduler.start()
    asyncio.create_task(check_upstream_health())
    
    try:
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


def refresh_exchange_rate():
    from app.services.exchange_rate_service import refresh_rate
    with SessionLocal() as db:
        refresh_rate(db)
