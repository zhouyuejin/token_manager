"""
操作日志服务
"""
import json
import secrets
from typing import Optional
from sqlalchemy.orm import Session
from loguru import logger

from app.models.operation_log import OperationLog
from app.models.user import User


def record_operation(
    db: Session,
    operator: User,
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """
    写入一条操作日志。不抛异常，失败仅 logger.exception。
    """
    try:
        log_entry = OperationLog(
            log_id=f"log_{secrets.token_hex(12)}",
            operator_id=operator.user_id,
            operator_name=operator.username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=json.dumps(detail, ensure_ascii=False) if detail is not None else None,
            ip_address=ip_address,
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        logger.exception("写入操作日志失败")
