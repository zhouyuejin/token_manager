"""
代理服务 - 核心中转功能

支持多渠道 Failover 和多 Key 轮询
"""
import json
import time
import secrets
import random
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set, Tuple
from functools import reduce
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


# 进程级 round_robin 计数器（重启归零）
_key_rr_counters: Dict[str, int] = {}


class ProxyService:
    """代理服务类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def verify_api_key(self, api_key: str) -> Optional[ApiKey]:
        """验证API Key"""
        key = self.db.query(ApiKey).filter(
            ApiKey.api_key == api_key,
            ApiKey.status == "active"
        ).first()
        return key
    
    def get_user_from_key(self, api_key: ApiKey) -> Optional[User]:
        """从API Key获取用户"""
        user = self.db.query(User).filter(
            User.user_id == api_key.user_id,
            User.status == "active"
        ).first()
        return user

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
        pool = [channel.api_key]
        if channel.extra_keys:
            try:
                extra = json.loads(channel.extra_keys)
                if isinstance(extra, list):
                    pool.extend(extra)
            except json.JSONDecodeError:
                pass
        return pool

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
                "status_code": 502,
                "error": "无可用渠道"
            }

        last_err = None
        attempted_channels = []

        for ch, mc, key in candidates:
            attempted_channels.append(ch.channel_id)
            try:
                result = self._forward_one(ch, mc.upstream_model, key, request_data)
                
                if result["success"]:
                    # 如果不是第一个候选，说明走了降级
                    if ch.channel_id != candidates[0][0].channel_id:
                        self.bump_channel_failure(ch)
                    return result
                
                status_code = result.get("status_code", 500)
                
                # 用户/认证错误：不重试
                if status_code in {400, 401, 403, 404}:
                    last_err = result
                    continue
                
                # 上游错误：重试下一个
                if status_code in {429, 500, 502, 503, 504}:
                    self.bump_key_failure(ch, key)
                    last_err = result
                    continue
                
                # 其它 4xx
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
        
        upstream_url = f"{channel.endpoint.rstrip('/')}/chat/completions"
        request_data["model"] = upstream_model
        
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

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
        
        Yields: SSE chunks
        """
        result = self.select_channel(model_id, user, api_key)
        
        if not result:
            yield 'data: {"error": "无可用渠道"}\n\n'
            yield "data: [DONE]\n\n"
            self._record_usage_failure(
                user_id=user.user_id,
                key_id=api_key.key_id,
                channel_id=None,
                model=model_id,
                status_code=502,
                error="无可用渠道"
            )
            return

        ch, upstream_model, key = result
        
        def generate():
            try:
                with httpx.Client(timeout=ch.timeout) as client:
                    upstream_url = f"{ch.endpoint.rstrip('/')}/chat/completions"
                    request_data["model"] = upstream_model
                    headers = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json"
                    }
                    
                    with client.stream("POST", upstream_url, json=request_data, headers=headers) as response:
                        if response.status_code != 200:
                            error_msg = f"HTTP {response.status_code}"
                            try:
                                error_data = response.json()
                                error_msg = (
                                    error_data.get("error", {}).get("message") or
                                    error_data.get("message") or
                                    error_data.get("detail") or
                                    error_msg
                                )
                            except:
                                pass
                            yield f'data: {{"error": "{error_msg}"}}\n\n'
                            yield "data: [DONE]\n\n"
                            return

                        for chunk in response.iter_lines():
                            if chunk:
                                yield chunk + "\n"
                                
            except Exception as e:
                yield f'data: {{"error": "{str(e)}"}}\n\n'
        
        return generate()

    def _record_usage_failure(
        self,
        user_id: str,
        key_id: str,
        channel_id: Optional[str],
        model: str,
        status_code: int,
        error: str
    ) -> None:
        """记录失败日志（不扣 quota）"""
        log_id = f"log_{secrets.token_hex(8)}"
        usage_log = UsageLog(
            log_id=log_id,
            user_id=user_id,
            key_id=key_id,
            channel_id=channel_id,
            model=model,
            total_tokens=0,
            latency_ms=0,
            status_code=status_code,
            error_message=error
        )
        self.db.add(usage_log)
        self.db.commit()

    def record_usage(
        self,
        user_id: str,
        key_id: str,
        channel_id: str,
        model: str,
        tokens: Dict[str, int],
        latency_ms: int,
        status_code: int,
        error_message: Optional[str] = None
    ) -> None:
        """记录用量日志"""
        log_id = f"log_{secrets.token_hex(8)}"
        
        usage_log = UsageLog(
            log_id=log_id,
            user_id=user_id,
            key_id=key_id,
            channel_id=channel_id,
            model=model,
            prompt_tokens=tokens.get("prompt_tokens", 0),
            completion_tokens=tokens.get("completion_tokens", 0),
            total_tokens=tokens.get("total_tokens", 0),
            latency_ms=latency_ms,
            status_code=status_code,
            error_message=error_message
        )
        
        self.db.add(usage_log)

    def calculate_tokens(self, request_data: Dict[str, Any], response_data: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
        """计算Token数量（估算）"""
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
        
        user.quota_used += total_tokens
        api_key.last_used_at = datetime.now()
        
        self.db.commit()
        
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
