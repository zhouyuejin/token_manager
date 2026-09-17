"""Key 项目授权的共享校验。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.organization import Department
from app.models.project import Project, UserProject

DEFAULT_PROJECT_ID = 'project_default'
DEFAULT_DEPARTMENT_ID = 'dept_default'


def require_user_project(db: Session, user_id: str, project_id: str) -> Project:
    project = db.query(Project).join(Department).join(UserProject).filter(
        Project.project_id == project_id, UserProject.user_id == user_id,
        Project.status == 'active', Department.status == 'active',
    ).first()
    if not project:
        raise HTTPException(status_code=403, detail='项目未授权或项目/部门已停用，请联系管理员分配可用项目')
    return project
