"""测试全局 fixtures。

两件事：
1) 解决 SQLite 不为 BigInteger 主键创建 ROWID 自增（替换为 TypeDecorator）。
2) 强制所有 sqlite:///:memory: 测试 engine 使用 StaticPool，避免多 connection 互相看不到表。
"""
import sqlalchemy
from sqlalchemy import Integer, TypeDecorator


class _BigIntegerCompat(TypeDecorator):
    """SQLite -> Integer（自增），MySQL -> BigInteger。"""
    impl = Integer
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name in ("mysql", "mariadb"):
            return dialect.type_descriptor(sqlalchemy.BigInteger())
        return dialect.type_descriptor(Integer())


# 在 import app.models 之前替换 BigInteger
sqlalchemy.BigInteger = _BigIntegerCompat

# 触发 app.models 加载
import app.models  # noqa: F401, E402

from sqlalchemy import create_engine as _sa_create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

_orig_create_engine = _sa_create_engine


def _patched_create_engine(url, **kwargs):
    """对 sqlite:///:memory: 强制 StaticPool + check_same_thread=False。"""
    url_str = str(url)
    if url_str.startswith("sqlite") and ":memory:" in url_str:
        kwargs.setdefault("connect_args", {})
        kwargs["connect_args"].setdefault("check_same_thread", False)
        kwargs.setdefault("poolclass", StaticPool)
    return _orig_create_engine(url, **kwargs)


# 替换 sqlalchemy.create_engine：影响所有测试文件里直接调 create_engine 的代码
sqlalchemy.create_engine = _patched_create_engine


import pytest  # noqa: E402
