from unittest.mock import AsyncMock, patch
import pytest
from app.core.config import settings
from app.services import email_service


@pytest.mark.asyncio
@pytest.mark.parametrize('port,tls,start_tls', [(465, True, False), (587, False, True)])
async def test_smtp_transport(port, tls, start_tls, monkeypatch):
    for key, value in {'SMTP_HOST': 'smtp.example.com', 'SMTP_USER': 'sender@example.com',
                       'SMTP_PASSWORD': 'test', 'SMTP_FROM_EMAIL': 'sender@example.com',
                       'SMTP_PORT': port}.items():
        monkeypatch.setattr(settings, key, value)
    with patch('app.services.email_service.aiosmtplib.send', new_callable=AsyncMock) as send:
        assert await email_service.send_email('user@example.com', '通知', '正文')
        assert send.call_args.kwargs['use_tls'] is tls
        assert send.call_args.kwargs['start_tls'] is start_tls


@pytest.mark.asyncio
async def test_notification_email_respects_preferences():
    from types import SimpleNamespace
    from app.models.notification import NotificationType
    from app.models.user import UserStatus
    user = SimpleNamespace(email='user@example.com', status=UserStatus.active,
                           quota_low_alert=False, quota_change_alert=True, daily_report=True)
    notif = SimpleNamespace(type=NotificationType.quota_low, title='额度不足', content='正文')
    with patch('app.services.email_service.send_email', new_callable=AsyncMock, return_value=True) as send:
        assert await email_service.send_notification_email(user, notif) is None
        send.assert_not_called()
        notif.type = NotificationType.system
        assert await email_service.send_notification_email(user, notif) is True
        send.assert_awaited_once_with(user.email, notif.title, notif.content)


@pytest.mark.asyncio
async def test_delivery_success_retry_and_skip(db, SessionLocal, monkeypatch):
    from app.models.user import User, UserRole, UserStatus
    from app.models.notification import Notification, NotificationType
    monkeypatch.setattr(settings, 'SMTP_HOST', 'smtp.example.com')
    monkeypatch.setattr(settings, 'SMTP_USER', 'sender@example.com')
    monkeypatch.setattr(settings, 'SMTP_PASSWORD', 'test')
    monkeypatch.setattr('app.core.database.SessionLocal', SessionLocal)
    user = User(user_id='usr_mail', username='mail', email='mail@example.com',
                password='test', role=UserRole.user, status=UserStatus.active,
                quota_low_alert=False)
    db.add(user)
    db.add_all([Notification(notif_id='mail_' + kind, user_id=user.user_id,
                            type=typ, title=kind, content='正文')
                for kind, typ in [('ok', NotificationType.system),
                                  ('retry', NotificationType.approval_result),
                                  ('skip', NotificationType.quota_low)]])
    db.commit()
    async def send(to, title, body):
        return title != 'retry'
    with patch('app.services.email_service.send_email', new_callable=AsyncMock, side_effect=send) as mail:
        for _ in range(4):
            await email_service.deliver_notification_emails()
        assert mail.await_count == 4  # success once, failure three times
    db.expire_all()
    rows = {n.title: n for n in db.query(Notification).all()}
    assert (rows['ok'].email_status, rows['ok'].email_attempts) == ('sent', 1)
    assert (rows['retry'].email_status, rows['retry'].email_attempts) == ('failed', 3)
    assert rows['skip'].email_status == 'skipped'


@pytest.mark.asyncio
async def test_unconfigured_smtp_does_not_consume_notifications(monkeypatch):
    monkeypatch.setattr(settings, 'SMTP_PASSWORD', '')
    with patch('app.core.database.SessionLocal') as session:
        await email_service.deliver_notification_emails()
        session.assert_not_called()


@pytest.mark.asyncio
async def test_smtp_failure_is_returned(monkeypatch):
    for key in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD'):
        monkeypatch.setattr(settings, key, 'test')
    with patch('app.services.email_service.aiosmtplib.send', new_callable=AsyncMock,
               side_effect=TimeoutError('test timeout')):
        assert await email_service.send_email('user@example.com', '通知', '正文') is False


def test_email_migration_does_not_backfill_history(db):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text
    from app.models.notification import Notification, NotificationType
    db.add(Notification(notif_id='historical', user_id='old', type=NotificationType.system,
                        title='历史通知'))
    db.commit()
    path = Path(__file__).parents[1] / 'alembic/versions/20261010_1100_notification_email.py'
    spec = importlib.util.spec_from_file_location('email_migration_test', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with db.get_bind().begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.downgrade()
        migration.upgrade()
        assert connection.execute(text("SELECT email_status FROM notifications WHERE notif_id='historical' ")).scalar() == 'skipped'
        connection.execute(text("INSERT INTO notifications (notif_id, user_id, type, title) VALUES ('new_mail', 'old', 'system', '新通知')"))
        assert connection.execute(text("SELECT email_status FROM notifications WHERE notif_id='new_mail'")).scalar() == 'pending'


def test_scheduler_uses_async_email_delivery():
    import inspect
    from app.services.scheduler_service import setup_scheduler, scheduler, check_quota_low_alert
    setup_scheduler()
    job = scheduler.get_job('deliver_notification_emails')
    assert inspect.iscoroutinefunction(job.func)
    assert job.max_instances == 1
    assert inspect.iscoroutinefunction(check_quota_low_alert)
    assert scheduler.get_job('send_daily_reports') is None
