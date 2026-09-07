"""
统一 datetime 字段类型：序列化时强制带 UTC 时区后缀。

背景：MySQL 容器是 UTC 时区，pymysql 返回 naive datetime，
Pydantic 默认序列化为 "2026-09-07T07:16:11"（无时区后缀），
前端 dayjs 会按本地时区解析，导致时间差 8 小时。

此类型在序列化时检测到 naive datetime 时附加 UTC tzinfo，
输出 "2026-09-07T07:16:11+00:00"（FastAPI 默认 jsonable_encoder
会进一步编码为 ISO 8601）。前端 dayjs / new Date 即可正确识别。
"""
from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer


def _to_utc_iso(v: datetime) -> datetime:
    """naive datetime 视为 UTC，aware datetime 保留原 tz。"""
    if v.tzinfo is None:
        return v.replace(tzinfo=timezone.utc)
    return v


# 序列化后类型保持 datetime，Pydantic 会继续走 ISO 编码。
UtcDateTime = Annotated[datetime, PlainSerializer(_to_utc_iso, return_type=datetime)]
