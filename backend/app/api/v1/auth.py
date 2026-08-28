"""
认证接口
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, generate_user_id
from app.models.user import User, UserRole, UserStatus

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# Schema
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class UserInfo(BaseModel):
    user_id: str
    username: str
    email: str
    role: str


@router.post("/register", response_model=UserInfo)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册"""
    # 检查用户名
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 检查邮箱
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    # 创建用户
    user = User(
        user_id=generate_user_id(),
        username=user_data.username,
        email=user_data.email,
        password=get_password_hash(user_data.password),
        role=UserRole.user,
        status=UserStatus.active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserInfo(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        role=user.role.value
    )


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """用户登录"""
    user = db.query(User).filter(User.username == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误"
        )
    
    if user.status == UserStatus.disabled:
        raise HTTPException(status_code=403, detail="账户已被禁用")
    
    # 生成Token
    access_token = create_access_token(data={"sub": user.user_id, "username": user.username})
    
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserInfo)
async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """获取当前用户"""
    from app.core.security import decode_access_token
    
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的令牌")
    
    user = db.query(User).filter(User.user_id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return UserInfo(
        user_id=user.user_id,
        username=user.username,
        email=user.email,
        role=user.role.value
    )
