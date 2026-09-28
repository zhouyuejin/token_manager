"""额度申请和审批接口。"""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.approval import ApprovalRequest
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.organization import Department
from app.models.project import Project, UserProject
from app.models.user import User
from app.schemas.approval import (ApiKeyApplicationCreate, ApprovalDecision, ApprovalSupplement,
                                  ModelGroupApplicationCreate, ProjectAccessApplicationCreate,
                                  QuotaApplicationCreate)
from app.services.api_key_approval_service import apply_api_key_approval
from app.services.approval_service import ApprovalService
from app.services.model_group_approval_service import apply_model_group_approval
from app.services.project_access_approval_service import apply_project_access_approval
from app.services.quota_approval_service import apply_quota_approval

router = APIRouter()


def _service(db):
    return ApprovalService(db, actions={
        'api_key': apply_api_key_approval,
        'quota': apply_quota_approval,
        'model_group': apply_model_group_approval,
        'project_access': apply_project_access_approval,
    })


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


@router.post('/model-group')
def create_model_group_application(
    data: ModelGroupApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _service(db).create_request(
        user, 'model_group', {'group_id': data.group_id}, data.reason,
        target_id=data.group_id,
    )


@router.get('/project-access/options')
def list_project_access_options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Project, Department.name).join(
        Department, Project.dept_id == Department.dept_id,
    ).outerjoin(
        UserProject,
        and_(UserProject.project_id == Project.project_id, UserProject.user_id == user.user_id),
    ).filter(
        Project.status == 'active', Department.status == 'active', UserProject.user_id.is_(None),
    ).order_by(Department.name, Project.name).all()
    return [{'project_id': project.project_id, 'name': project.name,
             'department_name': department_name, 'owner_user_id': project.owner_user_id}
            for project, department_name in rows]


@router.get('/model-group/options')
def list_model_group_application_options(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    granted_ids = set(json.loads(user.model_group_ids or '[]'))
    groups = db.query(ModelGroup).filter(ModelGroup.status == ModelGroupStatus.active).order_by(ModelGroup.name).all()
    return [{'group_id': group.group_id, 'name': group.name} for group in groups if group.group_id not in granted_ids]


@router.post('/project-access')
def create_project_access_application(
    data: ProjectAccessApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = db.query(Project).join(Department).filter(
        Project.project_id == data.project_id,
        Project.status == 'active', Department.status == 'active',
    ).first()
    if project is None:
        raise HTTPException(404, '项目不存在或已停用')
    if db.query(UserProject).filter_by(user_id=user.user_id, project_id=project.project_id).first():
        raise HTTPException(409, '您已拥有该项目权限')
    if db.query(ApprovalRequest).filter_by(
        requester_user_id=user.user_id, request_type='project_access',
        target_id=project.project_id, status='pending',
    ).first():
        raise HTTPException(409, '该项目已有待审批申请')
    approver_user_id = project.owner_user_id if project.owner_user_id != user.user_id else None
    return _service(db).create_request(
        user, 'project_access', {'project_id': project.project_id}, data.reason,
        target_id=project.project_id, approver_user_id=approver_user_id,
    )


@router.post('/api-key')
def create_api_key_application(
    data: ApiKeyApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from fastapi import HTTPException

    try:
        project = db.query(Project).filter_by(project_id=data.project_id).first()
        if project is None:
            raise HTTPException(404, '项目不存在')
        from app.services.project_service import require_user_project
        require_user_project(db, user.user_id, data.project_id)
        approver_user_id = project.owner_user_id if project.owner_user_id != user.user_id else None
        payload = data.model_dump(mode='json', exclude={'reason'})
        return _service(db).create_request(
            user, 'api_key', payload, data.reason, target_id=data.project_id,
            approver_user_id=approver_user_id,
        )
    except BaseException:
        db.rollback()
        raise


@router.get('/mine')
def list_my_applications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    requests = _service(db).list_my_requests(user)
    result = []
    consumed_secret = False
    for request in requests:
        item = {column.name: getattr(request, column.name) for column in request.__table__.columns}
        payload = dict(item['payload'])
        if request.request_type == 'api_key':
            secret_result = payload.pop('result', None)
            if secret_result and not payload.get('secret_consumed'):
                item['result'] = secret_result
                payload['secret_consumed'] = True
                consumed_secret = True
            item['payload'] = payload
            if secret_result and not request.payload.get('secret_consumed'):
                request.payload = payload
        result.append(item)
    if consumed_secret:
        db.commit()
    return result


@router.get('/pending')
def list_pending_applications(
    db: Session = Depends(get_db), admin: User = Depends(require_admin),
):
    return _service(db).list_pending(admin)


@router.get('/review')
def list_review_applications(
    db: Session = Depends(get_db),
    reviewer: User = Depends(get_current_user),
    request_type: str | None = None,
    status: str | None = None,
    requester_user_id: str | None = None,
    project_id: str | None = None,
):
    if request_type and request_type not in {'api_key', 'quota', 'model_group', 'project_access'}:
        raise HTTPException(422, '不支持的审批申请类型')
    if status and status not in {'pending', 'needs_info', 'approved', 'rejected', 'cancelled'}:
        raise HTTPException(422, '不支持的审批状态')
    requests = _service(db).list_review(reviewer, request_type, status, requester_user_id, project_id)
    result = []
    for request in requests:
        item = {column.name: getattr(request, column.name) for column in request.__table__.columns}
        if request.request_type == 'api_key':
            item['payload'] = {key: value for key, value in item['payload'].items()
                               if key not in {'result', 'secret_consumed'}}
        result.append(item)
    return result


@router.get('/review/requesters')
def list_review_requesters(
    db: Session = Depends(get_db), reviewer: User = Depends(get_current_user),
):
    query = db.query(User.user_id, User.username).join(
        ApprovalRequest, ApprovalRequest.requester_user_id == User.user_id,
    )
    if reviewer.role.value != 'admin':
        query = query.filter(ApprovalRequest.approver_user_id == reviewer.user_id)
    return [{'user_id': user_id, 'username': username} for user_id, username in
            query.distinct().order_by(User.username).all()]


@router.post('/{request_id}/decision')
def decide_application(
    request_id: str, data: ApprovalDecision,
    db: Session = Depends(get_db), reviewer: User = Depends(get_current_user),
):
    return _service(db).decide(reviewer, request_id, data.decision, data.comment)


@router.post('/{request_id}/cancel')
def cancel_my_application(
    request_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _service(db).cancel(user, request_id)


@router.post('/{request_id}/supplement')
def supplement_my_application(
    request_id: str, data: ApprovalSupplement,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return _service(db).supplement(user, request_id, data.content)
