"""
上游密钥加密工具。

使用 enc:v1: 前缀区分新密文和历史明文，便于旧渠道继续可用。
"""
import base64
import hashlib
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


ENCRYPTED_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    raw = settings.SECRET_ENCRYPTION_KEY or settings.SECRET_KEY
    try:
        key = raw.encode("utf-8")
        if len(key) == 44:
            return Fernet(key)
    except Exception:
        pass
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_encrypted_secret(value: Optional[str]) -> bool:
    return bool(value and value.startswith(ENCRYPTED_PREFIX))


def encrypt_secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if value == "":
        return ""
    if is_encrypted_secret(value):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_secret(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return value
    if not is_encrypted_secret(value):
        return value
    token = value[len(ENCRYPTED_PREFIX):].encode("utf-8")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("渠道密钥解密失败") from exc


def mask_secret(value: Optional[str]) -> str:
    plain = decrypt_secret(value) or ""
    if not plain:
        return ""
    if len(plain) <= 8:
        return "***"
    return f"{plain[:6]}...{plain[-4:]}"
