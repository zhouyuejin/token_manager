"""项目加入申请的生效动作。"""
from fastapi import HTTPException

from app.models.organization import Department
from app.models.project import Project, UserProject


def apply_project_access_approval(db, request):
    project = db.query(Project).join(Department).filter(
        Project.project_id == request.target_id,
        Project.status == 'active', Department.status == 'active',
    ).first()
    if project is None:
        raise HTTPException(409, '项目或所属部门已停用，无法授予权限')
    if not db.query(UserProject).filter_by(
        user_id=request.requester_user_id, project_id=request.target_id,
    ).first():
        db.add(UserProject(user_id=request.requester_user_id, project_id=request.target_id))
