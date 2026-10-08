"""
日志查询接口
"""
import json
import re
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.operation_log import OperationLog
from app.models.login_log import LoginLog
from app.models.route_decision_log import RouteDecisionLog
from app.dependencies import get_current_user, require_admin
from app.schemas.log import (
    OperationLogResponse,
    OperationLogListResponse,
    LoginLogResponse,
    LoginLogListResponse,
)
from app.services.content_privacy import redact_sensitive_text

router = APIRouter()


def _safe_route_error(value):
    if not value:
        return value
    if re.search(r"(?i)(api[_ -]?key|access[_ -]?token|bearer\s+|sk-[a-z0-9_-]{12,}|prompt|request\s*body|messages\s*[:=])", value):
        return "上游错误包含敏感内容，已隐藏"
    return redact_sensitive_text(value, 500)


@router.get("/routes")
async def list_route_decision_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    key_id: Optional[str] = None,
    model: Optional[str] = None,
    channel_id: Optional[str] = None,
    status_code: Optional[int] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    query = db.query(RouteDecisionLog)
    for column, value in (
        (RouteDecisionLog.request_id, request_id),
        (RouteDecisionLog.user_id, user_id),
        (RouteDecisionLog.key_id, key_id),
        (RouteDecisionLog.model, model),
        (RouteDecisionLog.status_code, status_code),
    ):
        if value is not None and value != "":
            query = query.filter(column == value)
    if channel_id:
        query = query.filter(
            (RouteDecisionLog.candidate_channels.like(f'%"{channel_id}"%')) |
            (RouteDecisionLog.selected_channel == channel_id) |
            (RouteDecisionLog.retry_path.like(f'%"channel_id": "{channel_id}"%'))
        )

    total = query.count()
    rows = query.outerjoin(User, User.user_id == RouteDecisionLog.user_id).with_entities(
        RouteDecisionLog, User.username
    ).order_by(
        RouteDecisionLog.created_at.desc(), RouteDecisionLog.id.desc()
    ).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "items": [{
            "id": row.id,
            "request_id": row.request_id,
            "user_id": row.user_id,
            "username": username,
            "key_id": row.key_id,
            "model": row.model,
            "candidate_channels": json.loads(row.candidate_channels),
            "skipped_reasons": json.loads(row.skipped_reasons),
            "selected_channel": row.selected_channel,
            "retry_path": json.loads(row.retry_path),
            "status_code": row.status_code,
            "success": row.success,
            "error_message": _safe_route_error(row.error_message),
            "created_at": row.created_at,
        } for row, username in rows],
    }

@router.get("/operations", response_model=OperationLogListResponse)
async def list_operation_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    operator_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    操作日志列表（管理员）
    """
    query = db.query(OperationLog)

    if keyword:
        query = query.filter(
            (OperationLog.operator_name.like(f"%{keyword}%")) |
            (OperationLog.detail.like(f"%{keyword}%"))
        )
    if action:
        query = query.filter(OperationLog.action == action)
    if target_type:
        query = query.filter(OperationLog.target_type == target_type)
    if operator_id:
        query = query.filter(OperationLog.operator_id == operator_id)
    if start_date and end_date:
        query = query.filter(
            func.date(OperationLog.created_at).between(start_date, end_date)
        )

    total = query.count()
    items = query.order_by(OperationLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    result_items = []
    for row in items:
        detail = None
        if row.detail:
            try:
                detail = json.loads(redact_sensitive_text(row.detail))
            except json.JSONDecodeError:
                detail = redact_sensitive_text(row.detail)
        result_items.append(
            OperationLogResponse(
                log_id=row.log_id,
                operator_id=row.operator_id,
                operator_name=redact_sensitive_text(row.operator_name, 50),
                action=row.action,
                target_type=row.target_type,
                target_id=row.target_id,
                detail=detail,
                ip_address=row.ip_address,
                created_at=row.created_at,
            )
        )

    return OperationLogListResponse(total=total, items=result_items)


@router.get("/logins", response_model=LoginLogListResponse)
async def list_login_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    登录日志列表（管理员）
    """
    query = db.query(LoginLog)

    if keyword:
        query = query.filter(LoginLog.username.like(f"%{keyword}%"))
    if status:
        query = query.filter(LoginLog.status == status)
    if start_date and end_date:
        query = query.filter(
            func.date(LoginLog.created_at).between(start_date, end_date)
        )

    total = query.count()
    items = query.order_by(LoginLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return LoginLogListResponse(
        total=total,
        items=[
            LoginLogResponse(
                log_id=row.log_id,
                username=redact_sensitive_text(row.username, 50),
                user_id=row.user_id,
                ip_address=row.ip_address,
                user_agent=row.user_agent,
                status=row.status,
                failure_reason=row.failure_reason,
                created_at=row.created_at,
            )
            for row in items
        ],
    )
