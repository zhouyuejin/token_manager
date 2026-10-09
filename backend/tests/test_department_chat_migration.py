"""迁移在测试库升级旧结构，并保护已产生的网页账目。"""
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect

from app.models.user import User
from app.models.usage_log import UsageLog


def migration(connection):
    path = Path(__file__).parents[1] / 'alembic/versions/20261009_1000_department_chat.py'
    spec = importlib.util.spec_from_file_location('department_chat_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(connection))
    return module


def test_upgrade_preserves_users_without_guessing_department(db, engine):
    db.add(User(user_id='old', username='old', email='old@test', password='hash'))
    db.commit()
    with engine.begin() as connection:
        change = migration(connection)
        change.downgrade()
        try:
            assert 'department_id' not in {c['name'] for c in inspect(connection).get_columns('users')}
        finally:
            change.upgrade()
        assert all(next(c for c in inspect(connection).get_columns(table) if c['name'] == 'key_id')['nullable']
                   for table in ('usage_logs', 'quota_reservations'))
    db.expire_all()
    assert db.query(User).filter_by(user_id='old').one().department_id is None


def test_downgrade_refuses_to_delete_or_forge_web_accounts(db, engine):
    db.add(UsageLog(log_id='web', user_id='old', key_id=None, project_id=None,
        department_id='dept', model='priced', status_code=200))
    db.commit()
    with engine.begin() as connection:
        with pytest.raises(RuntimeError, match='不能降级'):
            migration(connection).downgrade()
        assert next(c for c in inspect(connection).get_columns('usage_logs') if c['name'] == 'key_id')['nullable']
    assert db.query(UsageLog).one().key_id is None
