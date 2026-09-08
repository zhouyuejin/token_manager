"""Quota guard helpers — no transitive auth.py import."""
from fastapi import HTTPException


def ensure_can_adjust_amount(user) -> None:
    """Raise HTTPException(400) if user is currently unlimited."""
    if user.quota < 0:
        raise HTTPException(
            status_code=400,
            detail="该用户当前为无限制额度，请先取消无限制后再调整金额"
        )
