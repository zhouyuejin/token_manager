"""
安全工具
"""
from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import shortuuid

from app.core.config import settings

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 前端盐值（与前端约定保持一致）
FRONTEND_SALT = "token_manager_frontend_salt"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码 - 支持 bcrypt 和 SHA256 两种方式
    
    注意：前端已经对密码进行了 SHA256 哈希，所以这里直接比较哈希值
    """
    # 如果是 bcrypt 格式（以 $2b$ 开头）
    if hashed_password.startswith("$2b$"):
        return pwd_context.verify(plain_password, hashed_password)
    # 如果是 SHA256 格式（64位十六进制字符串），前端传的就是哈希值，直接比较
    elif len(hashed_password) == 64 and all(c in "0123456789abcdef" for c in hashed_password):
        return plain_password == hashed_password
    else:
        # 兼容旧的直接比较方式
        return plain_password == hashed_password


def get_password_hash(password: str) -> str:
    """获取密码哈希 - 优先使用 bcrypt"""
    return pwd_context.hash(password)


def hash_password_sha256(password: str) -> str:
    """对密码进行 SHA256 哈希（与前端保持一致）"""
    return hashlib.sha256(f"{FRONTEND_SALT}{password}".encode("utf-8")).hexdigest()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "jti": secrets.token_hex(8),  # 同秒内也能区分新旧 token
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """解码访问令牌"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_user_id() -> str:
    """生成用户ID"""
    return f"usr_{shortuuid.uuid()[:12]}"


def generate_key_id() -> str:
    """生成Key ID"""
    return f"key_{shortuuid.uuid()[:12]}"


def generate_api_key() -> str:
    """生成API Key"""
    return f"tmk_{shortuuid.uuid()}"


def hash_token(token: str) -> str:
    """SHA256(token) — 用于持久化敏感字符串（refresh token 等）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> tuple[str, str, str]:
    """
    生成新的 refresh token。
    返回 (plain, token_hash, token_id)。
    - plain: 返回给前端的明文，只此一次
    - token_hash: 存数据库
    - token_id: 业务 ID，便于日志和未来审计
    """
    plain = secrets.token_urlsafe(48)
    return plain, hash_token(plain), secrets.token_hex(8)
