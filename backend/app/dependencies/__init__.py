"""
通用依赖
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User, UserRole
from app.models.role_permission import RolePermission

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class TokenData(BaseModel):
    """Token解析后的数据"""
    user_id: str
    username: str


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """获取当前登录用户"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭证",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, username=username)
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.user_id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    
    if user.status.value == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用"
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    return current_user


def require_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """按当前操作检查角色权限；保留兼容旧路由的依赖名称。"""
    method = request.method.upper()
    path = request.url.path
    if current_user.role == UserRole.admin:
        return current_user

    if path.startswith("/api/v1/projects/admin"):
        permission = "department:read" if method == "GET" else "department:write"
    else:
        permission = "admin:read" if method == "GET" else "admin:write"
    allowed = db.query(RolePermission.permission).filter(
        RolePermission.role == current_user.role.value,
        RolePermission.permission == permission,
    ).first()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有执行此操作的权限"
        )
    return current_user
