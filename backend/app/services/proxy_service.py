"""
代理服务 - 核心中转功能

支持多渠道 Failover 和多 Key 轮询
"""
import json
import ipaddress
import time
import secrets
import random
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set, Tuple
from functools import reduce
from decimal import Decimal
import httpx
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.user import User
from app.models.user import UserRole
from app.models.api_key import ApiKey
from app.models.channel import Channel, ChannelStatus, ChannelHealthStatus
from app.models.model import Model, ModelStatus
from app.models.model_channel import ModelChannel
from app.models.model_group import ModelGroup, ModelGroupStatus, model_group_model_mappings
from app.models.usage_log import UsageLog
from app.models.project import Project
from app.services.project_service import DEFAULT_PROJECT_ID, DEFAULT_DEPARTMENT_ID

from app.services.channel_auth import build_auth_headers, get_upstream_url
from app.services.api_key_freeze_service import record_api_key_error, record_api_key_success
from app.services.secret_crypto import decrypt_secret


# 进程级 round_robin 计数器（重启归零）
_key_rr_counters: Dict[str, int] = {}


class ProxyService:
    """代理服务类"""
    
    def __init__(self, db: Session):
        self.db = db
        self.usage_attribution = {}
        self.stream_metadata = {}
        self.reservation_id = None

    def reserve_quota(self, user, api_key, model, request_data):
        from app.services.quota_reservation_service import QuotaReservationService
        from fastapi import HTTPException
        try:
            self.reservation_id = QuotaReservationService(self.db).reserve(
                user, api_key, model, request_data, self.capture_usage_attribution(api_key.key_id))
        except HTTPException as exc:
            if exc.status_code == 403:
                record_api_key_error(self.db, api_key, 'quota')
            raise
        return self.reservation_id

    def release_reservation(self):
        from app.services.quota_reservation_service import QuotaReservationService
        if self.reservation_id:
            self.db.rollback()
            QuotaReservationService(self.db).release(self.reservation_id)

    def reservation_lease(self):
        from app.services.quota_reservation_service import QuotaReservationService
        return QuotaReservationService(self.db).lease(self.reservation_id)
    
    def verify_api_key(self, api_key: str) -> Optional[ApiKey]:
        """验证API Key"""
        key, error = self.authenticate_api_key(api_key)
        return None if error else key

    def authenticate_api_key(self, api_key: str) -> Tuple[Optional[ApiKey], Optional[str]]:
        """返回 API Key 及不可用原因。"""
        key = self.db.query(ApiKey).filter(
            ApiKey.api_key == api_key
        ).first()
        if not key:
            return None, "无效的API Key"

        error = self.get_api_key_auth_error(key)
        if error:
            return key, error
        return key, None

    @staticmethod
    def get_api_key_auth_error(api_key: ApiKey) -> Optional[str]:
        status_value = getattr(getattr(api_key, "status", None), "value", getattr(api_key, "status", None))
        if status_value == "revoked" or getattr(api_key, "revoked_at", None):
            return "API Key已吊销"
        if getattr(api_key, "frozen_at", None):
            return "API Key已自动冻结，请联系管理员：" + (api_key.frozen_reason or "异常调用")
        if status_value != "active":
            return "无效的API Key"

        expires_at = getattr(api_key, "expires_at", None)
        if expires_at and expires_at <= datetime.utcnow():
            return "API Key已过期"
        return None
    
    def get_user_from_key(self, api_key: ApiKey) -> Optional[User]:
        """从API Key获取用户"""
        user = self.db.query(User).filter(
            User.user_id == api_key.user_id,
            User.status == "active"
        ).first()
        return user

    @staticmethod
    def check_api_key_ip(api_key: ApiKey, client_ip: Optional[str]) -> bool:
        """检查客户端 IP 是否命中 API Key 白名单。空白名单表示不限制。"""
        raw_whitelist = getattr(api_key, "ip_whitelist", None)
        if not raw_whitelist:
            return True

        try:
            whitelist = json.loads(raw_whitelist)
        except (TypeError, json.JSONDecodeError):
            return False

        if not whitelist:
            return True
        if not client_ip:
            return False

        try:
            ip = ipaddress.ip_address(client_ip)
        except ValueError:
            return False

        for item in whitelist:
            try:
                if "/" in item:
                    if ip in ipaddress.ip_network(item, strict=False):
                        return True
                elif ip == ipaddress.ip_address(item):
                    return True
            except (TypeError, ValueError):
                continue
        return False

    # ---- GC-1: single source of truth for model group access ----

    def get_effective_model_group_ids(self, user: User) -> Set[str]:
        """
        返回该用户可用的有效模型分组ID集合。
        """
        if user.role == UserRole.admin:
            return {
                g.group_id
                for g in self.db.query(ModelGroup)
                .filter(ModelGroup.status == ModelGroupStatus.active)
                .all()
            }

        default_groups = self.db.query(ModelGroup).filter(
            ModelGroup.is_default == 1,
            ModelGroup.status == "active"
        ).all()
        default_ids = {g.group_id for g in default_groups}
        user_ids: Set[str] = set(json.loads(user.model_group_ids or '[]'))
        return default_ids | user_ids

    def check_model_group_access(
        self,
        api_key: ApiKey,
        user: User,
        model_id: str
    ) -> Dict[str, Any]:
        """
        检查 api_key+user 组合是否有权访问 model_id。
        """
        effective_group_ids = self.get_effective_model_group_ids(user)

        model = self.db.query(Model).filter(
            Model.model_id == model_id,
            Model.status == ModelStatus.active
        ).first()

        if not model:
            return {
                "allowed": False,
                "reason": "model_not_found",
                "message": "当前 Key 未被授权访问该模型"
            }

        # 检查模型是否绑定了任何 enabled channel
        has_active_binding = self.db.query(ModelChannel).join(Channel).filter(
            ModelChannel.model_id == model_id,
            ModelChannel.enabled == True,
            Channel.status == ChannelStatus.active
        ).first()

        if not has_active_binding:
            return {
                "allowed": False,
                "reason": "model_no_active_channel",
                "message": "当前 Key 未被授权访问该模型"
            }

        if not effective_group_ids:
            return {
                "allowed": False,
                "reason": "no_effective_groups",
                "message": "当前 Key 未被授权访问该模型"
            }

        # 模型 → 分组（通过 model_group_model_mappings 表查询）
        bound_active_group_ids = set()
        group_mapping = self.db.query(
            model_group_model_mappings.c.group_id
        ).join(
            ModelGroup, ModelGroup.group_id == model_group_model_mappings.c.group_id
        ).filter(
            model_group_model_mappings.c.model_id == model_id,
            ModelGroup.status == ModelGroupStatus.active
        ).all()
        bound_active_group_ids = {g.group_id for g in group_mapping}

        if not bound_active_group_ids:
            return {
                "allowed": False,
                "reason": "model_not_bound",
                "message": "当前 Key 未被授权访问该模型"
            }

        if not effective_group_ids & bound_active_group_ids:
            return {
                "allowed": False,
                "reason": "group_mismatch",
                "message": "当前 Key 未被授权访问该模型"
            }

        return {"allowed": True}

    def check_quota(self, user: User, api_key: ApiKey, estimated_tokens: int = 1000) -> Dict[str, Any]:
        """检查额度是否充足，返回详细原因"""
        quota_remain = user.quota - user.quota_used

        if user.role == UserRole.admin:
            return {
                "allowed": True,
                "reason": "admin_unlimited",
                "message": "管理员账户为无限制额度",
            }

        if user.quota < 0:
            return {
                "allowed": True,
                "reason": "unlimited",
                "message": "您使用的是无限制额度。"
            }

        if user.quota == 0:
            return {
                "allowed": False,
                "reason": "quota_zero",
                "message": "您的账户额度为 0，请联系管理员分配额度后再试。"
            }

        if quota_remain < estimated_tokens:
            return {
                "allowed": False,
                "reason": "quota_insufficient",
                "message": f"额度不足，当前剩余 {quota_remain} tokens，请联系管理员充值。"
            }

        return {"allowed": True}

    # ========== 新增：Failover + 多 Key 路由 ==========

    def select_channel(
        self,
        model_id: str,
        user: User,
        api_key: ApiKey
    ) -> Optional[Tuple[Channel, str, str]]:
        """
        选择最佳渠道。

        Returns: (Channel, upstream_model, key_used) or None
        """
        now = datetime.now()
        
        # 查询候选：Model → ModelChannel → Channel
        candidates = (
            self.db.query(ModelChannel, Channel)
            .join(Channel, Channel.channel_id == ModelChannel.channel_id)
            .filter(
                ModelChannel.model_id == model_id,
                ModelChannel.enabled == True,
                Channel.status == ChannelStatus.active,
                (Channel.health_status == None) | (Channel.health_status != ChannelHealthStatus.unhealthy),
                # 过滤 cooldown
                (Channel.cooldown_until == None) | (Channel.cooldown_until < now)
            )
            .order_by(
                # 按 max(channel.priority, mc.priority) 降序
                func.greatest(Channel.priority, ModelChannel.priority).desc(),
                ModelChannel.weight.desc(),
                Channel.channel_id.asc()
            )
            .all()
        )

        if not candidates:
            return None

        # 选择第一个（最高优先级）
        mc, ch = candidates[0]
        
        # 选择 key
        key = self.pick_key(ch)
        
        return (ch, mc.upstream_model, key)

    def select_candidates(
        self,
        model_id: str,
        user: User,
        api_key: ApiKey
    ) -> List[Tuple[Channel, ModelChannel, str]]:
        """
        获取所有候选渠道（用于 failover）。
        """
        now = datetime.now()
        
        candidates = (
            self.db.query(ModelChannel, Channel)
            .join(Channel, Channel.channel_id == ModelChannel.channel_id)
            .filter(
                ModelChannel.model_id == model_id,
                ModelChannel.enabled == True,
                Channel.status == ChannelStatus.active,
                (Channel.health_status == None) | (Channel.health_status != ChannelHealthStatus.unhealthy),
                (Channel.cooldown_until == None) | (Channel.cooldown_until < now)
            )
            .order_by(
                func.greatest(Channel.priority, ModelChannel.priority).desc(),
                ModelChannel.weight.desc(),
                Channel.channel_id.asc()
            )
            .all()
        )

        result = []
        for mc, ch in candidates:
            key = self.pick_key(ch)
            result.append((ch, mc, key))
        
        return result

    def pick_key(self, channel: Channel) -> str:
        """
        从 channel 的 key 池中选择一个 key。
        
        策略: round_robin / random / sequential
        """
        pool = self._get_key_pool(channel)
        if not pool:
            raise ValueError(f"Channel {channel.channel_id} has no keys")

        health = json.loads(channel.key_health or '{}')
        alive_keys = [k for k in pool if not self._is_key_in_cooldown(health, k)]
        
        # 全 cooldown 时退而求其次
        if not alive_keys:
            alive_keys = pool

        strategy = channel.key_strategy or 'round_robin'
        
        if strategy == 'round_robin':
            counter = _key_rr_counters.get(channel.channel_id, 0)
            key = alive_keys[counter % len(alive_keys)]
            _key_rr_counters[channel.channel_id] = counter + 1
            return key
        elif strategy == 'random':
            return random.choice(alive_keys)
        else:  # sequential
            return alive_keys[0]

    def _get_key_pool(self, channel: Channel) -> List[str]:
        """获取 channel 的所有 key"""
        pool = [decrypt_secret(channel.api_key)]
        if channel.extra_keys:
            try:
                extra = json.loads(channel.extra_keys)
                if isinstance(extra, list):
                    pool.extend(decrypt_secret(k) for k in extra)
            except json.JSONDecodeError:
                pass
        return [k for k in pool if k]

    def _key_fingerprint(self, key: str) -> str:
        """Key 的哈希指纹（用于存储在 key_health 中）"""
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _is_key_in_cooldown(self, health: Dict, key: str) -> bool:
        """检查 key 是否在 cooldown 中"""
        fp = self._key_fingerprint(key)
        rec = health.get(fp, {})
        if rec.get("cooldown_until"):
            try:
                cooldown = datetime.fromisoformat(rec["cooldown_until"])
                if cooldown > datetime.now():
                    return True
            except (ValueError, TypeError):
                pass
        return False

    def bump_key_failure(self, channel: Channel, key: str) -> None:
        """
        记录 key 失败。
        5 次失败 → 60s cooldown。
        """
        health = json.loads(channel.key_health or '{}')
        fp = self._key_fingerprint(key)
        rec = health.get(fp, {"failure_count": 0, "cooldown_until": None})
        rec["failure_count"] += 1
        
        if rec["failure_count"] >= 5:
            rec["cooldown_until"] = (datetime.now() + timedelta(seconds=60)).isoformat()
            rec["failure_count"] = 0
        
        health[fp] = rec
        channel.key_health = json.dumps(health)
        # 不单独 commit，由调用方整体 commit

    def bump_channel_failure(self, channel: Channel) -> None:
        """
        记录 channel 失败（降级）。
        设置 60s cooldown。
        """
        channel.cooldown_until = datetime.now() + timedelta(seconds=60)

    def forward_with_failover(
        self,
        model_id: str,
        user: User,
        api_key: ApiKey,
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        带 failover 的转发。
        
        - 4xx (非429): 继续下一 channel
        - 5xx/429/超时: 触发 key/cooldown，继续下一 channel
        """
        self.capture_usage_attribution(api_key.key_id)
        candidates = self.select_candidates(model_id, user, api_key)
        
        if not candidates:
            self._record_usage_failure(
                user_id=user.user_id,
                key_id=api_key.key_id,
                channel_id=None,
                model=model_id,
                status_code=502,
                error="无可用渠道"
            )
            return {
                "success": False,
                "usage_recorded": True,
                "status_code": 502,
                "error": "无可用渠道"
            }

        last_err = None
        attempted_channels = []

        for ch, mc, key in candidates:
            attempted_channels.append(ch.channel_id)
            try:
                with self.reservation_lease():
                    result = self._forward_one(ch, mc.upstream_model, key, request_data)
                
                if result["success"]:
                    record_api_key_success(api_key)
                    # 如果不是第一个候选，说明走了降级
                    if ch.channel_id != candidates[0][0].channel_id:
                        self.bump_channel_failure(ch)
                    return result
                
                status_code = result.get("status_code", 500)
                if 400 <= status_code < 500:
                    record_api_key_error(self.db, api_key, "upstream_4xx")
                
                # 用户/认证错误：不重试
                if status_code in {400, 401, 403, 404}:
                    last_err = result
                    continue
                
                # 上游错误：重试下一个
                if status_code in {429, 500, 502, 503, 504}:
                    self.bump_key_failure(ch, key)
                    last_err = result
                    continue
                
                # 其它 4xx 同样需要留存失败归因。
                self._record_usage_failure(user.user_id, api_key.key_id, ch.channel_id, model_id, status_code, result.get("error"))
                result["usage_recorded"] = True
                return result
                
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                self.bump_key_failure(ch, key)
                last_err = {"success": False, "status_code": 504, "error": str(e)}
                continue

        # 全部失败
        self._record_usage_failure(
            user_id=user.user_id,
            key_id=api_key.key_id,
            channel_id=attempted_channels[-1] if attempted_channels else None,
            model=model_id,
            status_code=last_err.get("status_code", 502) if last_err else 502,
            error=f"已尝试 {len(attempted_channels)} 个渠道，全部失败：{last_err.get('error') if last_err else '未知错误'}"
        )
        
        return {
            "success": False,
            "usage_recorded": True,
            "channel_id": attempted_channels[-1] if attempted_channels else None,
            "status_code": last_err.get("status_code", 502) if last_err else 502,
            "error": f"已尝试 {len(attempted_channels)} 个渠道，仍失败"
        }

    def _forward_one(
        self,
        channel: Channel,
        upstream_model: str,
        key: str,
        request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """单次转发到上游"""
        start_time = time.time()
        
        request_data["model"] = upstream_model
        upstream_url = get_upstream_url(channel, model=upstream_model)

        headers = build_auth_headers(channel, key)
        headers["Content-Type"] = "application/json"
        if channel.upstream_format == "anthropic" or (channel.upstream_format == "auto" and channel.type.value == "anthropic"):
            headers.setdefault("anthropic-version", "2023-06-01")

        try:
            with httpx.Client(timeout=channel.timeout) as client:
                response = client.post(
                    upstream_url,
                    json=request_data,
                    headers=headers
                )
                
                latency_ms = int((time.time() - start_time) * 1000)
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "status_code": 200,
                        "data": response.json() if response.text else {},
                        "latency_ms": latency_ms,
                        "error": None,
                        "channel_id": channel.channel_id,
                        "upstream_model": upstream_model
                    }
                else:
                    error_msg = f"HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if isinstance(error_data, dict):
                            error_msg = (
                                error_data.get("error", {}).get("message") or
                                error_data.get("message") or
                                error_data.get("detail") or
                                error_msg
                            )
                    except:
                        pass
                    
                    # 记录成功（以便统计），但标记为非 200
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "data": {},
                        "latency_ms": latency_ms,
                        "error": error_msg,
                        "channel_id": channel.channel_id,
                        "upstream_model": upstream_model
                    }
                
        except httpx.TimeoutException:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "status_code": 504,
                "data": {},
                "latency_ms": latency_ms,
                "error": "上游请求超时"
            }
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "status_code": 500,
                "data": {},
                "latency_ms": latency_ms,
                "error": str(e)
            }

    def forward_stream(
        self,
        model_id: str,
        user: User,
        api_key: ApiKey,
        request_data: Dict[str, Any]
    ):
        """
        流式转发（不做 failover）。
        返回一个生成器，yield SSE chunks。
        """
        self.capture_usage_attribution(api_key.key_id)
        result = self.select_channel(model_id, user, api_key)

        self.stream_metadata = {"channel_id": None, "status_code": 502, "error": "无可用渠道", "recorded": False}
        if not result:
            self._record_usage_failure(
                user_id=user.user_id,
                key_id=api_key.key_id,
                channel_id=None,
                model=model_id,
                status_code=502,
                error="无可用渠道"
            )

            self.stream_metadata["recorded"] = True

            def empty():
                yield 'data: {"error": "无可用渠道"}\n\n'
                yield "data: [DONE]\n\n"
            return empty()

        ch, upstream_model, key = result
        self.stream_metadata.update(channel_id=ch.channel_id, status_code=502, error=None)
        start_time = time.time()

        def generate():
            completion_text = ""
            try:
                with self.reservation_lease(), httpx.Client(timeout=ch.timeout) as client:
                    request_data["model"] = upstream_model
                    request_data["stream"] = True
                    upstream_url = get_upstream_url(ch, model=upstream_model)
                    headers = build_auth_headers(ch, key)
                    headers["Content-Type"] = "application/json"
                    if ch.upstream_format == "anthropic" or (ch.upstream_format == "auto" and ch.type.value == "anthropic"):
                        headers.setdefault("anthropic-version", "2023-06-01")

                    with client.stream("POST", upstream_url, json=request_data, headers=headers) as response:
                        self.stream_metadata["status_code"] = response.status_code
                        if response.status_code != 200:
                            if 400 <= response.status_code < 500:
                                record_api_key_error(self.db, api_key, "upstream_4xx")
                            # stream 上下文需先读 body 才能解析 JSON 错误
                            error_msg = f"HTTP {response.status_code}"
                            try:
                                error_text = response.read().decode("utf-8")
                                error_data = json.loads(error_text)
                                error_msg = (
                                    error_data.get("error", {}).get("message")
                                    or error_data.get("message")
                                    or error_data.get("detail")
                                    or error_text[:300]
                                    or error_msg
                                )
                            except Exception:
                                pass
                            self.stream_metadata["error"] = error_msg
                            safe_error = error_msg.replace("\\", "\\\\").replace('"', '\\"')
                            yield f'data: {{"error": "{safe_error}"}}\n\n'
                            yield "data: [DONE]\n\n"
                            return

                        record_api_key_success(api_key)
                        for chunk in response.iter_lines():
                            if chunk:
                                if chunk.startswith('data: ') and chunk[6:].strip() != '[DONE]':
                                    try:
                                        data = json.loads(chunk[6:])
                                        if data.get('error'):
                                            self.stream_metadata.update(status_code=502, error=str(data['error']))
                                        if data.get('usage'):
                                            self.stream_metadata['tokens'] = self.calculate_tokens(request_data, data)
                                        for choice in data.get('choices', []):
                                            completion_text += choice.get('delta', {}).get('content') or ''
                                    except (ValueError, TypeError, AttributeError):
                                        pass
                                yield chunk + "\n"
                        if 'tokens' not in self.stream_metadata:
                            self.stream_metadata['tokens'] = self.calculate_tokens(request_data, {'choices': [{'message': {'content': completion_text}}]})
                        self.stream_metadata['completed'] = True

            except Exception as e:
                self.stream_metadata.update(status_code=502, error=str(e))
                yield f'data: {{"error": "{str(e)}"}}\n\n'
                yield "data: [DONE]\n\n"

            finally:
                self.stream_metadata["latency_ms"] = int((time.time() - start_time) * 1000)

        return generate()

    def capture_usage_attribution(self, key_id: str):
        """保存请求开始时的归属，防止调用期间编辑 Key 改写历史。"""
        if key_id not in self.usage_attribution:
            key = self.db.query(ApiKey).filter(ApiKey.key_id == key_id).first()
            project_id = key.project_id if key and key.project_id else DEFAULT_PROJECT_ID
            project = self.db.query(Project).filter(Project.project_id == project_id).first()
            self.usage_attribution[key_id] = {
                "project_id": project_id,
                "department_id": project.dept_id if project else DEFAULT_DEPARTMENT_ID,
            }
        return self.usage_attribution[key_id]

    def _usage_cost(self, model_id, channel_id, tokens, status_code):
        if status_code != 200:
            return Decimal('0')
        model = self.db.query(Model).filter(Model.model_id == model_id).first()
        if not model and channel_id:
            model = self.db.query(Model).join(ModelChannel).filter(
                ModelChannel.channel_id == channel_id, ModelChannel.upstream_model == model_id,
            ).first()
        if not model:
            return Decimal('0')
        if getattr(model.price_type, 'value', model.price_type) == 'request':
            return Decimal(model.price_per_request or 0)
        return (Decimal(tokens.get('prompt_tokens', 0)) * Decimal(model.price_per_1k_input or 0)
                + Decimal(tokens.get('completion_tokens', 0)) * Decimal(model.price_per_1k_output or 0)) / 1000

    def _record_usage_failure(self, user_id, key_id, channel_id, model, status_code, error):
        """失败记录使用同一归因路径，费用为零。"""
        self.record_usage(user_id, key_id, channel_id, model, {}, 0, status_code, error)
        self.db.commit()

    def record_usage(
        self, user_id: str, key_id: str, channel_id: Optional[str], model: str,
        tokens: Dict[str, int], latency_ms: int, status_code: int,
        error_message: Optional[str] = None,
        attribution: Optional[Dict[str, str]] = None,
    ) -> None:
        """记录归因和费用快照；字段不会随项目归属或价格变化重算。"""
        usage_cost = self._usage_cost(model, channel_id, tokens, status_code)
        if self.reservation_id:
            from app.models.quota_reservation import QuotaReservation
            from app.services.quota_reservation_service import cost
            reservation = self.db.get(QuotaReservation, self.reservation_id)
            usage_cost = cost(reservation, tokens) if status_code == 200 else Decimal('0')
            attribution = {'project_id': reservation.project_id, 'department_id': reservation.department_id}
        usage_log = UsageLog(
            log_id=f"log_{secrets.token_hex(8)}", user_id=user_id, key_id=key_id,
            channel_id=channel_id, model=model,
            **(attribution or self.capture_usage_attribution(key_id)),
            cost_usd=usage_cost,
            prompt_tokens=tokens.get("prompt_tokens", 0),
            completion_tokens=tokens.get("completion_tokens", 0),
            total_tokens=tokens.get("total_tokens", 0),
            latency_ms=latency_ms, status_code=status_code, error_message=error_message,
        )
        self.db.add(usage_log)

    def calculate_tokens(self, request_data: Dict[str, Any], response_data: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """计算Token数量（估算）"""
        usage = response_data.get('usage') if response_data else None
        if usage and ('prompt_tokens' in usage or 'completion_tokens' in usage):
            prompt = int(usage.get('prompt_tokens', 0) or 0)
            completion = int(usage.get('completion_tokens', 0) or 0)
            return {'prompt_tokens': prompt, 'completion_tokens': completion,
                    'total_tokens': int(usage.get('total_tokens', prompt + completion) or 0)}
        prompt_tokens = 0
        completion_tokens = 0
        
        if "messages" in request_data:
            for msg in request_data["messages"]:
                if "content" in msg:
                    prompt_tokens += len(msg["content"]) // 4
        
        if response_data and "choices" in response_data:
            for choice in response_data["choices"]:
                if "message" in choice and "content" in choice["message"]:
                    completion_tokens += len(choice["message"]["content"]) // 4
        
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
    
    async def deduct_quota(
        self,
        user: User,
        api_key: ApiKey,
        tokens: Dict[str, int]
    ) -> None:
        """扣减额度"""
        total_tokens = tokens.get("total_tokens", 0)
        if self.reservation_id:
            from app.services.quota_reservation_service import QuotaReservationService
            if not QuotaReservationService(self.db).commit(self.reservation_id, tokens):
                raise RuntimeError('预扣状态已终结，无法结算')
        else:
            from sqlalchemy import update
            self.db.execute(update(User).where(User.user_id == user.user_id).values(quota_used=User.quota_used + total_tokens))
            api_key.last_used_at = datetime.now()
            self.db.commit()
        self.db.refresh(user)
        
        quota_remain = user.quota - user.quota_used
        if user.quota > 0 and quota_remain / user.quota <= 0.2 and user.quota_low_alert:
            from app.services.notification_service import create_notification
            from app.models.notification import NotificationType
            try:
                await create_notification(
                    db=self.db,
                    user_id=user.user_id,
                    notif_type=NotificationType.quota_low,
                    title="额度不足警告",
                    content=f"您的剩余额度已低于20%，当前剩余 {quota_remain} tokens，请及时充值。",
                    metadata={"quota_remain": quota_remain, "quota_total": user.quota}
                )
            except Exception:
                pass
        
        if total_tokens > 1000 and user.quota_change_alert:
            from app.services.notification_service import create_notification
            from app.models.notification import NotificationType
            try:
                await create_notification(
                    db=self.db,
                    user_id=user.user_id,
                    notif_type=NotificationType.quota_decrease,
                    title="额度已扣减",
                    content=f"本次消费 {total_tokens} tokens，当前剩余 {quota_remain} tokens。",
                    metadata={"deducted": total_tokens, "quota_remain": quota_remain}
                )
            except Exception:
                pass


def create_proxy_service(db: Session) -> ProxyService:
    """创建代理服务实例"""
    return ProxyService(db)
