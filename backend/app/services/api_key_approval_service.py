"""API Key 申请的审批生效动作。"""
import json
import secrets
from datetime import datetime

from fastapi import HTTPException

from app.models.api_key import ApiKey, ApiKeyStatus
from app.services.project_service import require_user_project


def apply_api_key_approval(db, request):
    payload = dict(request.payload)
    project_id = payload.get('project_id')
    require_user_project(db, request.requester_user_id, project_id)
    name = payload.get('name')
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(422, 'Key 用途不能为空')
    ip_whitelist = payload.get('ip_whitelist', [])
    if not isinstance(ip_whitelist, list) or any(not isinstance(ip, str) for ip in ip_whitelist):
        raise HTTPException(422, 'IP 白名单格式无效')
    expires_at = payload.get('expires_at')
    if expires_at:
        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))

    api_key = f"tmk_{secrets.token_hex(16)}"
    key = ApiKey(
        key_id=f"key_{secrets.token_hex(8)}", user_id=request.requester_user_id,
        api_key=api_key, key_name=name.strip(), project_id=project_id,
        ip_whitelist=json.dumps(ip_whitelist), expires_at=expires_at,
        qps_limit=0, rpm_limit=0, tpm_limit=0, concurrency_limit=0,
        status=ApiKeyStatus.active,
    )
    db.add(key)
    db.flush()
    payload['result'] = {'key_id': key.key_id, 'api_key': api_key}
    request.payload = payload
