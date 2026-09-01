"""
每日用量报表定时任务
"""
import asyncio
from datetime import datetime, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from app.core.database import SessionLocal
from app.models.user import User
from app.models.usage_log import UsageLog
from app.services.notification_service import create_notification
from app.models.notification import NotificationType

scheduler = AsyncIOScheduler()


def get_today_usage(user_id: str, db) -> dict:
    """统计用户今日用量"""
    today = date.today()
    logs = db.query(UsageLog).filter(
        UsageLog.user_id == user_id,
        UsageLog.created_at >= today
    ).all()
    
    total_tokens = sum(log.total_tokens or 0 for log in logs)
    total_requests = len(logs)
    
    return {
        "tokens": total_tokens,
        "requests": total_requests,
        "date": today.isoformat()
    }


async def send_daily_reports():
    """每天 23:59 发送每日报表给所有开启此功能的用户"""
    db = SessionLocal()
    try:
        # 查找所有开启每日报表的用户
        users = db.query(User).filter(User.daily_report == True).all()
        
        for user in users:
            try:
                usage = get_today_usage(user.user_id, db)
                
                await create_notification(
                    db=db,
                    user_id=user.user_id,
                    notif_type=NotificationType.daily_report,
                    title="每日用量报表",
                    content=f"今日使用 {usage['tokens']} tokens，共 {usage['requests']} 次请求",
                    metadata=usage
                )
                logger.info(f"已发送每日报表给用户 {user.user_id}")
            except Exception as e:
                logger.exception(f"发送每日报表失败 user={user.user_id}")
        
        logger.info(f"每日报表任务完成，共处理 {len(users)} 个用户")
    finally:
        db.close()


def init_scheduler():
    """初始化定时任务调度器"""
    # 每天 23:59 执行
    scheduler.add_job(
        send_daily_reports,
        CronTrigger(hour=23, minute=59),
        id="daily_report",
        name="每日用量报表",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("每日报表定时任务已启动")


def shutdown_scheduler():
    """关闭调度器（应用退出时调用）"""
    scheduler.shutdown()
    logger.info("每日报表定时任务已关闭")
