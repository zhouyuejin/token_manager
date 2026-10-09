"""
认证接口
"""
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urljoin

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from loguru import logger
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.core.database import get_db
from app.core.config import settings
from app.core.security import (
    decode_access_token,
    verify_password, create_access_token,
    generate_user_id, generate_refresh_token, hash_token,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole, UserStatus
from app.models.login_log import LoginLog
from app.models.role_permission import RolePermission
from app.schemas.user import Nickname
from app.utils.request import extract_client_ip, extract_user_agent
from app.services.content_privacy import redact_sensitive_text
from jose import JWTError, jwt

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
    token_type: str = "bearer"
    refresh_token: str
    expires_in: int  # access_token 剩余秒数


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None  # 不传则只登出前端


class UserInfo(BaseModel):
    user_id: str
    username: str
    nickname: Nickname = None
    avatar_url: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    department_status: Optional[str] = None
    email: str
    role: str


@router.post("/register", response_model=UserInfo)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """用户注册 - 密码已在前端进行 SHA256 哈希"""
    if not settings.PASSWORD_LOGIN_ENABLED:
        raise HTTPException(status_code=403, detail="账号密码登录已关闭")
    # 检查用户名
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 检查邮箱
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    # 前端已对密码进行 SHA256 哈希，直接存储
    # 使用 SHA256 哈希值存储（不再使用 bcrypt）
    password_hash = user_data.password  # 已经是前端哈希后的值

    # 新注册用户自动分配默认模型分组
    from app.models.model_group import get_unique_default_group
    import json
    default_group = get_unique_default_group(db)
    if default_group:
        model_group_ids = json.dumps([default_group.group_id])
    else:
        model_group_ids = '[]'
    
    # 创建用户
    user = User(
        user_id=generate_user_id(),
        username=user_data.username,
        email=user_data.email,
        password=password_hash,
        role=UserRole.user,
        status=UserStatus.active,
        model_group_ids=model_group_ids,
        quota=settings.DEFAULT_NEW_USER_QUOTA,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # 通知所有管理员有新用户注册
    from app.services.notification_service import notify_admins_new_user
    await notify_admins_new_user(db, user)
    
    return UserInfo(
        user_id=user.user_id,
        username=user.username,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        department_id=user.department_id,
        department_name=user.department.name if user.department else None,
        department_status=user.department.status if user.department else None,
        email=user.email,
        role=user.role.value
    )


def _create_login_log(db: Session, username: str, user_id: Optional[str],
                      ip: Optional[str], ua: Optional[str],
                      login_status: str, failure_reason: Optional[str] = None) -> None:
    """写入登录日志，失败不抛出异常。"""
    try:
        log = LoginLog(
            log_id=secrets.token_hex(16),
            username=redact_sensitive_text(username, 50),
            user_id=user_id,
            ip_address=ip,
            user_agent=ua,
            status=login_status,
            failure_reason=failure_reason,
        )
        db.add(log)
        db.commit()
    except Exception:
        logger.exception("写入登录日志失败")


@router.post("/login", response_model=Token)
async def login(request: Request, db: Session = Depends(get_db)):
    """用户登录 - 密码已在前端进行 SHA256 哈希
    
    支持两种请求格式：
    1. JSON: {"username": "xxx", "password": "xxx"}
    2. Form: username=xxx&password=xxx
    """
    if not settings.PASSWORD_LOGIN_ENABLED:
        raise HTTPException(status_code=403, detail="账号密码登录已关闭")
    # 手动解析请求体，支持 JSON 和 form-urlencoded
    content_type = request.headers.get("Content-Type", "")
    username = ""
    password = ""
    
    if "application/json" in content_type:
        try:
            body = await request.json()
            username = body.get("username", "")
            password = body.get("password", "")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="无效的 JSON 格式"
            )
    elif "application/x-www-form-urlencoded" in content_type:
        try:
            form = await request.form()
            username = form.get("username", "")
            password = form.get("password", "")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="无效的表单数据"
            )
    else:
        # 尝试自动检测格式
        try:
            body = await request.json()
            username = body.get("username", "")
            password = body.get("password", "")
        except Exception:
            try:
                form = await request.form()
                username = form.get("username", "")
                password = form.get("password", "")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="无法解析请求数据，请发送 JSON 或 form-urlencoded 格式"
                )
    ip_address = extract_client_ip(request)
    user_agent = extract_user_agent(request)

    try:
        user = db.query(User).filter(User.username == username).first()

        if not user:
            _create_login_log(db, username, None, ip_address, user_agent,
                              "failed", "user_not_found")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )

        # 验证密码（前端传递的已经是 SHA256 哈希后的值）
        if not verify_password(password, user.password):
            _create_login_log(db, username, user.user_id, ip_address, user_agent,
                              "failed", "invalid_password")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误"
            )

        if user.status == UserStatus.disabled:
            _create_login_log(db, username, user.user_id, ip_address, user_agent,
                              "blocked", "account_disabled")
            raise HTTPException(status_code=403, detail="账户已被禁用")

        # 生成Token
        access_token = create_access_token(data={"sub": user.user_id, "username": user.username})

        _create_login_log(db, username, user.user_id, ip_address, user_agent, "success")

        # 生成 refresh token 并入库
        plain, h, token_id = generate_refresh_token()
        refresh_row = RefreshToken(
            token_id=token_id,
            user_id=user.user_id,
            token_hash=h,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
        db.add(refresh_row)
        db.commit()

        return Token(
            access_token=access_token,
            token_type="bearer",
            refresh_token=plain,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("登录过程异常")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误"
        )


def oidc_enabled() -> bool:
    return bool(settings.OIDC_ISSUER_URL and settings.OIDC_CLIENT_ID and
                settings.OIDC_CLIENT_SECRET and settings.OIDC_REDIRECT_URI and
                settings.OIDC_FRONTEND_URL)


async def oidc_metadata(client: httpx.AsyncClient) -> dict:
    issuer = settings.OIDC_ISSUER_URL.rstrip("/")
    response = await client.get(f"{issuer}/.well-known/openid-configuration")
    response.raise_for_status()
    metadata = response.json()
    if metadata.get("issuer", "").rstrip("/") != issuer:
        raise ValueError("OIDC issuer mismatch")
    return metadata


@router.get("/oidc/config")
async def oidc_config():
    return {"oidc_enabled": oidc_enabled(), "password_login_enabled": settings.PASSWORD_LOGIN_ENABLED}


@router.get("/oidc/login")
async def oidc_login():
    if not oidc_enabled():
        raise HTTPException(status_code=404, detail="企业登录未配置")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            metadata = await oidc_metadata(client)
    except Exception:
        logger.exception("读取 OIDC 配置失败")
        raise HTTPException(status_code=502, detail="企业登录服务暂不可用")

    nonce = secrets.token_urlsafe(24)
    state = jwt.encode({"sub": "oidc", "nonce": nonce}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    query = urlencode({
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    })
    response = RedirectResponse(f"{metadata['authorization_endpoint']}?{query}")
    response.set_cookie(
        "oidc_state", state, max_age=300, httponly=True,
        secure=settings.OIDC_REDIRECT_URI.startswith("https://"),
        samesite="lax", path="/api/v1/auth/oidc",
    )
    return response


def _oidc_user(db: Session, claims: dict) -> User:
    subject = f"{settings.OIDC_ISSUER_URL.rstrip('/')}|{claims['sub']}"
    user = db.query(User).filter(User.oidc_subject == subject).first()
    if user:
        return user

    email = claims.get("email", "").strip().lower()
    if not email or claims.get("email_verified") is not True:
        raise HTTPException(status_code=403, detail="企业账号未提供已验证邮箱")
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.oidc_subject = subject
        db.commit()
        return user

    base = (claims.get("preferred_username") or email.split("@", 1)[0]).strip()[:50] or "oidc-user"
    username = base
    suffix = 1
    while db.query(User.user_id).filter(User.username == username).first():
        suffix += 1
        username = f"{base[:45]}-{suffix}"
    from app.models.model_group import get_unique_default_group
    default_group = get_unique_default_group(db)
    import json
    user = User(
        user_id=generate_user_id(), username=username, email=email,
        password=hashlib.sha256(secrets.token_bytes(32)).hexdigest(),
        role=UserRole.user, status=UserStatus.active,
        model_group_ids=json.dumps([default_group.group_id]) if default_group else "[]",
        quota=settings.DEFAULT_NEW_USER_QUOTA, oidc_subject=subject,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/oidc/callback")
async def oidc_callback(request: Request, code: str, state: str, db: Session = Depends(get_db)):
    if not oidc_enabled():
        raise HTTPException(status_code=404, detail="企业登录未配置")
    if not state or state != request.cookies.get("oidc_state"):
        raise HTTPException(status_code=400, detail="OIDC state 无效")
    try:
        state_claims = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if state_claims.get("sub") != "oidc":
            raise JWTError("invalid state")
        async with httpx.AsyncClient(timeout=10) as client:
            metadata = await oidc_metadata(client)
            token_response = await client.post(
                metadata["token_endpoint"],
                data={"grant_type": "authorization_code", "code": code,
                      "redirect_uri": settings.OIDC_REDIRECT_URI, "client_id": settings.OIDC_CLIENT_ID},
                auth=(settings.OIDC_CLIENT_ID, settings.OIDC_CLIENT_SECRET),
            )
            token_response.raise_for_status()
            id_token = token_response.json()["id_token"]
            header = jwt.get_unverified_header(id_token)
            if header.get("alg") != "RS256":
                raise JWTError("unsupported signing algorithm")
            jwks_response = await client.get(metadata["jwks_uri"])
            jwks_response.raise_for_status()
            signing_key = next((key for key in jwks_response.json()["keys"]
                                if key.get("kid") == header.get("kid")), None)
            if signing_key is None:
                raise JWTError("signing key not found")
            claims = jwt.decode(
                id_token, signing_key, algorithms=["RS256"],
                audience=settings.OIDC_CLIENT_ID, issuer=metadata["issuer"],
            )
        if claims.get("nonce") != state_claims.get("nonce"):
            raise JWTError("nonce mismatch")
        user = _oidc_user(db, claims)
        if user.status == UserStatus.disabled:
            raise HTTPException(status_code=403, detail="账户已被禁用")

        ip_address = extract_client_ip(request)
        user_agent = extract_user_agent(request)
        _create_login_log(db, user.username, user.user_id, ip_address, user_agent, "success")
        access_token = create_access_token(data={"sub": user.user_id, "username": user.username})
        plain, token_hash, token_id = generate_refresh_token()
        db.add(RefreshToken(
            token_id=token_id, user_id=user.user_id, token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ))
        db.commit()
        fragment = urlencode({"access_token": access_token, "refresh_token": plain})
        response = RedirectResponse(f"{settings.OIDC_FRONTEND_URL.rstrip('/')}/login#{fragment}")
        response.delete_cookie("oidc_state", path="/api/v1/auth/oidc")
        return response
    except HTTPException:
        raise
    except (JWTError, KeyError, StopIteration, httpx.HTTPError, ValueError):
        logger.exception("OIDC 登录校验失败")
        raise HTTPException(status_code=401, detail="企业登录验证失败")


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    """获取当前用户信息"""
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="无效的令牌")
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="无效的令牌")
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return UserInfo(
        user_id=user.user_id,
        username=user.username,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        department_id=user.department_id,
        department_name=user.department.name if user.department else None,
        department_status=user.department.status if user.department else None,
        email=user.email,
        role=user.role.value
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(refresh_req: RefreshRequest, db: Session = Depends(get_db)):
    """刷新访问令牌"""
    refresh_token_str = refresh_req.refresh_token
    
    # 查找 refresh token
    token_hash = hash_token(refresh_token_str)
    token_record = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.expires_at > datetime.utcnow()
    ).first()
    
    if not token_record:
        raise HTTPException(status_code=401, detail="无效的刷新令牌")
    
    # 获取用户
    user = db.query(User).filter(User.user_id == token_record.user_id).first()
    if not user or user.status != UserStatus.active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")
    
    # 生成新的 access token
    access_token = create_access_token(data={"sub": user.user_id, "username": user.username})
    
    # 生成新的 refresh token
    new_plain, new_hash, new_token_id = generate_refresh_token()
    
    # 删除旧的 refresh token
    db.delete(token_record)
    
    # 创建新的 refresh token
    new_refresh = RefreshToken(
        token_id=new_token_id,
        user_id=user.user_id,
        token_hash=new_hash,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(new_refresh)
    db.commit()
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        refresh_token=new_plain,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/logout")
async def logout(logout_req: LogoutRequest, db: Session = Depends(get_db)):
    """登出"""
    if logout_req.refresh_token:
        token_hash = hash_token(logout_req.refresh_token)
        db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).delete()
        db.commit()
    return {"message": "登出成功"}
