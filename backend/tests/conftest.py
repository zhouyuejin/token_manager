"""测试全局 fixtures（MySQL）。"""
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

import app.models  # noqa: F401, E402
from app.core.database import Base


TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+pymysql://token_user:token_password@mysql:3306/token_db_test?charset=utf8mb4",
)


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(bind=eng)
    with eng.begin() as connection:
        upgrade_cny_schema(connection)
    return eng


@pytest.fixture(scope="session")
def SessionLocal(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _truncate_all(db: Session):
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        db.execute(text(f"TRUNCATE TABLE {table.name}"))
        db.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    db.commit()


@pytest.fixture
def db(engine, SessionLocal):
    session = SessionLocal()
    _truncate_all(session)
    try:
        yield session
    finally:
        session.close()


def upgrade_cny_schema(connection):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'alembic/versions/20261009_1100_cny_billing.py'
    spec = importlib.util.spec_from_file_location('cny_schema', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = Operations(MigrationContext.configure(connection))
    migration.upgrade()
