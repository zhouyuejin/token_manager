"""
日志查询接口
"""
import json
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.operation_log import OperationLog
from app.models.login_log import LoginLog
from app.dependencies import get_current_user, require_admin
from app.schemas.log import (
    OperationLogResponse,
    OperationLogListResponse,
    LoginLogResponse,
    LoginLogListResponse,
)

router = APIRouter()

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
                detail = json.loads(row.detail)
            except json.JSONDecodeError:
                detail = row.detail
        result_items.append(
            OperationLogResponse(
                log_id=row.log_id,
                operator_id=row.operator_id,
                operator_name=row.operator_name,
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
                username=row.username,
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
