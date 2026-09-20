"""部门、项目维护及项目成员分配。"""
import secrets
from typing import Literal, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.models.organization import Department
from app.models.project import Project, UserProject
from app.models.api_key import ApiKey
from app.models.usage_log import UsageLog
from app.models.quota_reservation import QuotaReservation
from app.models.budget import Budget
from app.services.operation_log_service import record_operation
from app.utils.request import extract_client_ip

router = APIRouter()


class DepartmentSave(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    owner_user_id: Optional[str] = None
    status: Literal['active', 'disabled'] = 'active'

    @field_validator('name')
    @classmethod
    def nonblank_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('名称不能为空')
        return value


class ProjectSave(DepartmentSave):
    dept_id: str = Field(min_length=1, max_length=32)


class ProjectUsers(BaseModel):
    user_ids: List[str]


def department_response(row):
    return {field: getattr(row, field) for field in ('dept_id', 'name', 'owner_user_id', 'status')}


def project_response(row):
    return {**{field: getattr(row, field) for field in ('project_id', 'dept_id', 'name', 'owner_user_id', 'status')},
            'department_name': row.department.name}


def get_project(db, project_id):
    row = db.query(Project).filter(Project.project_id == project_id).first()
    if not row:
        raise HTTPException(404, '项目不存在')
    return row


def check_owner(db, owner_id):
    if owner_id and not db.query(User).filter(User.user_id == owner_id).first():
        raise HTTPException(404, '负责人不存在')


def audit(db, request, admin, action, target_type, target_id, detail):
    record_operation(db=db, operator=admin, action=action, target_type=target_type,
                     target_id=target_id, detail=detail, ip_address=extract_client_ip(request))


@router.get('')
async def list_available_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.query(Project).join(UserProject).join(Department).options(joinedload(Project.department)).filter(
        UserProject.user_id == current_user.user_id, Project.status == 'active', Department.status == 'active',
    ).all()
    return {'items': [project_response(row) for row in rows]}


@router.get('/admin/departments')
async def list_departments(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {'items': [department_response(row) for row in db.query(Department).all()]}


@router.post('/admin/departments')
async def create_department(data: DepartmentSave, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    check_owner(db, data.owner_user_id)
    row = Department(dept_id='dept_' + secrets.token_hex(8), **data.model_dump())
    db.add(row)
    db.commit()
    audit(db, request, admin, 'create', 'department', row.dept_id, data.model_dump())
    return department_response(row)


@router.put('/admin/departments/{dept_id}')
async def update_department(dept_id: str, data: DepartmentSave, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(Department).filter(Department.dept_id == dept_id).first()
    if not row:
        raise HTTPException(404, '部门不存在')
    check_owner(db, data.owner_user_id)
    for field, value in data.model_dump().items():
        setattr(row, field, value)
    db.commit()
    audit(db, request, admin, 'update', 'department', dept_id, data.model_dump())
    return department_response(row)


@router.delete('/admin/departments/{dept_id}')
async def delete_department(dept_id: str, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.query(Department).filter(Department.dept_id == dept_id).first()
    if not row:
        raise HTTPException(404, '部门不存在')
    if db.query(Project.project_id).filter(Project.dept_id == dept_id).first():
        raise HTTPException(409, '部门下存在项目，请先处理项目')
    if (db.query(UsageLog.log_id).filter(UsageLog.department_id == dept_id).first()
            or db.query(QuotaReservation.reservation_id).filter(QuotaReservation.department_id == dept_id).first()
            or db.query(Budget.budget_id).filter(Budget.scope_type == 'department', Budget.scope_id == dept_id).first()):
        raise HTTPException(409, '部门已有历史归因或预算数据，请改为停用')
    db.delete(row)
    db.commit()
    audit(db, request, admin, 'delete', 'department', dept_id, {'name': row.name})
    return {'message': '删除成功'}


@router.get('/admin')
async def list_projects(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Project).options(joinedload(Project.department)).all()
    return {'items': [project_response(row) for row in rows]}


@router.post('/admin')
async def create_project(data: ProjectSave, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not db.query(Department).filter(Department.dept_id == data.dept_id).first():
        raise HTTPException(404, '部门不存在')
    check_owner(db, data.owner_user_id)
    row = Project(project_id='project_' + secrets.token_hex(8), **data.model_dump())
    db.add(row)
    db.commit()
    audit(db, request, admin, 'create', 'project', row.project_id, data.model_dump())
    return project_response(row)


@router.put('/admin/{project_id}')
async def update_project(project_id: str, data: ProjectSave, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = get_project(db, project_id)
    if not db.query(Department).filter(Department.dept_id == data.dept_id).first():
        raise HTTPException(404, '部门不存在')
    check_owner(db, data.owner_user_id)
    for field, value in data.model_dump().items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    audit(db, request, admin, 'update', 'project', project_id, data.model_dump())
    return project_response(row)


@router.delete('/admin/{project_id}')
async def delete_project(project_id: str, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    row = get_project(db, project_id)
    if db.query(UserProject.user_id).filter(UserProject.project_id == project_id).first():
        raise HTTPException(409, '项目已分配用户，请先撤销分配')
    if db.query(ApiKey.key_id).filter(ApiKey.project_id == project_id).first():
        raise HTTPException(409, '项目已有关联 Key，请改为停用')
    if (db.query(UsageLog.log_id).filter(UsageLog.project_id == project_id).first()
            or db.query(QuotaReservation.reservation_id).filter(QuotaReservation.project_id == project_id).first()
            or db.query(Budget.budget_id).filter(Budget.scope_type == 'project', Budget.scope_id == project_id).first()):
        raise HTTPException(409, '项目已有历史归因或预算数据，请改为停用')
    detail = {'name': row.name, 'dept_id': row.dept_id}
    db.delete(row)
    db.commit()
    audit(db, request, admin, 'delete', 'project', project_id, detail)
    return {'message': '删除成功'}


@router.get('/admin/{project_id}/users')
async def get_project_users(project_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    get_project(db, project_id)
    rows = db.query(User.user_id, User.username).join(UserProject, UserProject.user_id == User.user_id).filter(UserProject.project_id == project_id).all()
    return {'user_ids': [row.user_id for row in rows], 'items': [{'user_id': row.user_id, 'username': row.username} for row in rows]}


@router.put('/admin/{project_id}/users')
async def set_project_users(project_id: str, data: ProjectUsers, request: Request, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    get_project(db, project_id)
    user_ids = set(data.user_ids)
    found = {row.user_id for row in db.query(User.user_id).filter(User.user_id.in_(user_ids)).all()}
    if found != user_ids:
        raise HTTPException(404, '分配的用户不存在')
    db.query(UserProject).filter(UserProject.project_id == project_id).delete(synchronize_session=False)
    db.add_all([UserProject(user_id=user_id, project_id=project_id) for user_id in user_ids])
    db.commit()
    audit(db, request, admin, 'update', 'project', project_id, {'user_ids': sorted(user_ids)})
    return {'message': '项目分配成功'}


@router.get('/admin/users/{user_id}/available')
async def get_user_available_projects(user_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Project).join(UserProject).join(Department).filter(
        UserProject.user_id == user_id, Project.status == 'active', Department.status == 'active',
    ).all()
    return {'items': [project_response(row) for row in rows]}
