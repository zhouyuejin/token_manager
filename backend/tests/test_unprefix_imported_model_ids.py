"""Exercise the data migration against a small relational database."""
import importlib.util
import sqlite3
import sys
import types
from pathlib import Path
from unittest.mock import patch


class Database:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, params=()):
        cursor = self.connection.execute(statement, params)
        return types.SimpleNamespace(
            mappings=lambda: types.SimpleNamespace(all=lambda: cursor.fetchall()),
            first=lambda: cursor.fetchone(),
        )


def test_unprefix_imported_model_ids_merges_channels_and_groups():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        PRAGMA foreign_keys = ON;
        CREATE TABLE models (
            model_id TEXT PRIMARY KEY, display_name TEXT, description TEXT,
            aliases TEXT, price_type TEXT, price_per_1k_input REAL,
            price_per_1k_output REAL, price_per_request REAL, status TEXT,
            route_strategy TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE channels (channel_id TEXT PRIMARY KEY, type TEXT);
        CREATE TABLE model_channels (
            model_id TEXT REFERENCES models(model_id), channel_id TEXT,
            upstream_model TEXT, priority INTEGER, weight INTEGER,
            enabled INTEGER, created_at TEXT, updated_at TEXT,
            UNIQUE (model_id, channel_id)
        );
        CREATE TABLE model_group_model_mappings (
            group_id TEXT, model_id TEXT REFERENCES models(model_id),
            created_at TEXT, UNIQUE (group_id, model_id)
        );
        CREATE TABLE chat_conversations (model_id TEXT);
        INSERT INTO models (model_id, display_name) VALUES
            ('minimax-MiniMax-M2', 'MiniMax-M2'),
            ('openai-MiniMax-M2', 'MiniMax-M2'),
            ('minimax-custom', 'custom');
        INSERT INTO channels VALUES ('ch_m', 'minimax'), ('ch_o', 'openai');
        INSERT INTO model_channels (model_id, channel_id, upstream_model) VALUES
            ('minimax-MiniMax-M2', 'ch_m', 'MiniMax-M2'),
            ('openai-MiniMax-M2', 'ch_o', 'MiniMax-M2'),
            ('minimax-custom', 'ch_m', 'different-name');
        INSERT INTO model_group_model_mappings VALUES
            ('group_a', 'minimax-MiniMax-M2', NULL),
            ('group_b', 'openai-MiniMax-M2', NULL);
        INSERT INTO chat_conversations VALUES ('minimax-MiniMax-M2');
    """)

    op = types.ModuleType("alembic")
    op.op = types.SimpleNamespace(get_bind=lambda: Database(db))
    sa = types.ModuleType("sqlalchemy")
    sa.text = lambda statement: statement
    migration_path = Path(__file__).resolve().parents[1] / "alembic/versions/20261008_1200_unprefix_imported_model_ids.py"
    spec = importlib.util.spec_from_file_location("unprefix_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"alembic": op, "sqlalchemy": sa}):
        spec.loader.exec_module(migration)
        migration.upgrade()

    assert [row[0] for row in db.execute("SELECT model_id FROM models ORDER BY model_id")] == [
        "MiniMax-M2", "minimax-custom"
    ]
    assert [tuple(row) for row in db.execute("SELECT model_id, channel_id FROM model_channels ORDER BY channel_id")] == [
        ("MiniMax-M2", "ch_m"), ("minimax-custom", "ch_m"), ("MiniMax-M2", "ch_o")
    ]
    assert [tuple(row) for row in db.execute("SELECT group_id, model_id FROM model_group_model_mappings ORDER BY group_id")] == [
        ("group_a", "MiniMax-M2"), ("group_b", "MiniMax-M2")
    ]
    assert db.execute("SELECT model_id FROM chat_conversations").fetchone()[0] == "MiniMax-M2"


if __name__ == "__main__":
    test_unprefix_imported_model_ids_merges_channels_and_groups()
