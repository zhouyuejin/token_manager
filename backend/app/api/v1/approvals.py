"""额度申请和审批接口。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.approval import ApprovalRequest
from app.models.user import User
from app.schemas.approval import ApprovalDecision, QuotaApplicationCreate
from app.services.approval_service import ApprovalService
from app.services.quota_approval_service import apply_quota_approval

router = APIRouter()


def _service(db):
    return ApprovalService(db, actions={'quota': apply_quota_approval})


@router.post('/quota')
def create_quota_application(
    data: QuotaApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.quota < 0:
        from fastapi import HTTPException
        raise HTTPException(400, '无限制额度用户无需申请额度')
    if not data.reason.strip():
        from fastapi import HTTPException
        raise HTTPException(422, '申请理由不能为空')
    return _service(db).create_request(
        user, 'quota', {'amount': data.amount}, data.reason.strip(),
    )


@router.get('/mine')
def list_my_applications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _service(db).list_my_requests(user)


@router.get('/pending')
def list_pending_applications(
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    return _service(db).list_pending(admin)


@router.post('/{request_id}/decision')
def decide_application(
    request_id: str, data: ApprovalDecision,
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    return _service(db).decide(admin, request_id, data.decision, data.comment)
