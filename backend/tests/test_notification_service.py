"""notify_admins_new_user 单元测试"""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import app
from app.models.user import User, UserRole, UserStatus
from app.models.notification import Notification, NotificationType
from app.core.security import hash_password_sha256

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://token_user:token_password@mysql:3306/token_db_test?charset=utf8mb4",
)
engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(__import__("sqlalchemy").text("SET FOREIGN_KEY_CHECKS=0"))
            db.execute(__import__("sqlalchemy").text(f"TRUNCATE TABLE {table.name}"))
            db.execute(__import__("sqlalchemy").text("SET FOREIGN_KEY_CHECKS=1"))
        db.commit()
    finally:
        db.close()


def _create_admin(db, username="admin", email="admin@test.com"):
    admin = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=hash_password_sha256("adminpass"),
        role=UserRole.admin,
        status=UserStatus.active,
    )
    db.add(admin)
    db.commit()
    return admin


def _create_user(db, username="newuser", email="newuser@test.com", quota=0):
    user = User(
        user_id=f"usr_{username}",
        username=username,
        email=email,
        password=hash_password_sha256("userpass"),
        role=UserRole.user,
        status=UserStatus.active,
        quota=quota,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestNotifyAdminsNewUser:
    """notify_admins_new_user 单元测试"""

    def test_normal_case_sends_notification_to_all_admins(self):
        """正常情况：有一个管理员，发送一条通知"""
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db, username="admin1", email="admin1@test.com")
            user = _create_user(db, username="newuser1", email="newuser1@test.com")

            from app.services.notification_service import notify_admins_new_user
            import asyncio
            asyncio.run(notify_admins_new_user(db, user))

            notifs = db.query(Notification).filter(
                Notification.user_id == admin.user_id
            ).all()
            assert len(notifs) == 1
            assert notifs[0].type == NotificationType.user_registered
            assert notifs[0].title == "新用户注册"
            assert "newuser1" in notifs[0].content
            assert "newuser1@test.com" in notifs[0].content
            import json
            meta = json.loads(notifs[0].extra_data) if notifs[0].extra_data else {}
            assert meta.get("user_id") == user.user_id
            assert meta.get("username") == "newuser1"
        finally:
            db.close()

    def test_multiple_admins_each_gets_notification(self):
        """多个管理员，每个都收到通知"""
        db = TestingSessionLocal()
        try:
            admin1 = _create_admin(db, username="admin1", email="admin1@test.com")
            admin2 = _create_admin(db, username="admin2", email="admin2@test.com")
            user = _create_user(db, username="newuser2", email="newuser2@test.com")

            from app.services.notification_service import notify_admins_new_user
            import asyncio
            asyncio.run(notify_admins_new_user(db, user))

            notifs = db.query(Notification).filter(
                Notification.user_id.in_([admin1.user_id, admin2.user_id])
            ).all()
            assert len(notifs) == 2
        finally:
            db.close()

    def test_no_admin_no_error(self):
        """无管理员时，不抛异常"""
        db = TestingSessionLocal()
        try:
            user = _create_user(db, username="alone", email="alone@test.com")

            from app.services.notification_service import notify_admins_new_user
            import asyncio
            # Should NOT raise
            asyncio.run(notify_admins_new_user(db, user))

            count = db.query(Notification).count()
            assert count == 0
        finally:
            db.close()

    def test_notification_failure_does_not_raise(self):
        """通知发送失败时，吞掉异常，不向上抛出"""
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db, username="safe_admin", email="safe@test.com")
            user = _create_user(db, username="boom", email="boom@test.com")

            with patch("app.services.notification_service.create_notification", side_effect=Exception("DB error")):
                from app.services.notification_service import notify_admins_new_user
                import asyncio
                # Should NOT raise
                asyncio.run(notify_admins_new_user(db, user))
        finally:
            db.close()

    def test_notification_failure_does_not_poison_session(self):
        """通知 flush 失败时，调用方的 db session 仍可继续使用（SAVEPOINT 隔离）

        回归测试：notifications.type 列若缺少 user_registered，INSERT 会失败；
        savepoint 必须隔离这次失败，否则 session 被毒化，/register 读 user 属性
        时会触发 PendingRollbackError 导致 500。
        """
        from sqlalchemy import text
        db = TestingSessionLocal()
        try:
            admin = _create_admin(db, username="safe_admin2", email="safe2@test.com")
            user = _create_user(db, username="boom_user2", email="boom_u2@test.com")

            # 临时把 notifications.type 改回不含 user_registered，
            # 复现未迁移的状态（这就是 /register 之前 500 的真实场景）
            db.execute(text(
                "ALTER TABLE notifications "
                "MODIFY COLUMN type ENUM('quota_low','quota_increase','quota_decrease','daily_report','system') NOT NULL"
            ))
            db.commit()

            try:
                from app.services.notification_service import notify_admins_new_user
                import asyncio
                # 不应抛异常
                asyncio.run(notify_admins_new_user(db, user))

                # 关键断言：session 仍然可用，可以继续操作
                # 如果 savepoint 没生效，这里会触发 PendingRollbackError
                count = db.query(User).count()
                assert count == 2  # admin + user

                # 还能做后续写操作（模拟 /register 里 db.refresh + 读 user 属性）
                extra = User(
                    user_id="usr_extra",
                    username="extra",
                    email="extra@test.com",
                    password=hash_password_sha256("x"),
                    role=UserRole.user,
                    status=UserStatus.active,
                )
                db.add(extra)
                db.commit()
                db.refresh(extra)
                # 读 user 属性不能触发 PendingRollbackError
                assert extra.username == "extra"
            finally:
                # 恢复 enum，避免影响其他测试
                db.execute(text(
                    "ALTER TABLE notifications "
                    "MODIFY COLUMN type ENUM('quota_low','quota_increase','quota_decrease','daily_report','system','user_registered') NOT NULL"
                ))
                db.commit()
        finally:
            db.close()
