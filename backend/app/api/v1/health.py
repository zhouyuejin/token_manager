"""管理员渠道健康看板接口。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import require_admin
from app.models.channel import Channel
from app.models.user import User
from app.services.operation_log_service import record_operation
from app.services.route_health_service import RouteHealthService
from app.utils.request import extract_client_ip

router = APIRouter()


@router.get("/channels")
async def get_channel_health(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return {"items": RouteHealthService(db).get_channel_health()}


@router.post("/channels/{channel_id}/recover")
async def recover_channel_health(
    channel_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    channel = db.query(Channel).filter(Channel.channel_id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    RouteHealthService(db).recover_channel(channel)
    record_operation(
        db=db,
        operator=admin,
        action="recover_cooldown",
        target_type="channel",
        target_id=channel_id,
        detail={"channel_id": channel_id, "channel_cooldown": True, "key_cooldowns": True},
        ip_address=extract_client_ip(request),
    )
    return {"message": "渠道 cooldown 已恢复"}
