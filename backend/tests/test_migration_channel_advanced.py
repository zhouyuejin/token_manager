"""
验证 channels 表新增字段存在且默认值正确
"""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


def test_upstream_format_column_exists(db: Session):
    result = db.execute(text("SHOW COLUMNS FROM channels LIKE 'upstream_format'"))
    row = result.fetchone()
    assert row is not None, "upstream_format 列不存在"
    assert row[1] == "varchar(32)"
    assert "chat" in row[4].lower()


def test_auth_type_column_exists(db: Session):
    result = db.execute(text("SHOW COLUMNS FROM channels LIKE 'auth_type'"))
    row = result.fetchone()
    assert row is not None
    assert row[1] == "varchar(32)"
    assert "auto" in row[4].lower()


def test_auth_headers_column_exists(db: Session):
    result = db.execute(text("SHOW COLUMNS FROM channels LIKE 'auth_headers'"))
    row = result.fetchone()
    assert row is not None
    assert "text" in row[1].lower() or "json" in row[1].lower()


def test_existing_channel_works_without_new_fields(db: Session):
    """存量数据无新字段值时仍能正常工作（依赖 server_default）"""
    db.execute(text("""
        INSERT INTO channels (channel_id, name, type, endpoint, api_key, status, health_status, key_strategy)
        VALUES ('ch_test', 'test', 'openai', 'https://api.openai.com', 'sk-test', 'active', 'healthy', 'round_robin')
    """))
    db.commit()
    result = db.execute(text("SELECT upstream_format, auth_type FROM channels WHERE channel_id = 'ch_test'"))
    row = result.fetchone()
    assert row[0] == "chat"
    assert row[1] == "auto"
