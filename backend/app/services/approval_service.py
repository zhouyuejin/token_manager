"""审批申请的创建、查询和单级决策。"""
import json
import secrets
from datetime import datetime

from fastapi import HTTPException

from app.models.approval import ApprovalRequest
from app.models.operation_log import OperationLog
from app.models.notification import Notification, NotificationType
from app.models.user import User, UserRole
from loguru import logger


REQUEST_TYPES = {'api_key', 'quota', 'model_group', 'project_access'}


class ApprovalService:
    def __init__(self, db, actions=None):
        self.db = db
        self.actions = actions or {}

    def create_request(self, requester, request_type, payload, reason, target_id=None, approver_user_id=None):
        if request_type not in REQUEST_TYPES:
            raise HTTPException(422, '不支持的审批申请类型')
        if not isinstance(payload, dict):
            raise HTTPException(422, '申请内容必须是对象')
        request = ApprovalRequest(
            request_id=secrets.token_hex(16), request_type=request_type,
            requester_user_id=requester.user_id, approver_user_id=approver_user_id,
            target_id=target_id, payload=payload, reason=reason, status='pending',
        )
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def list_my_requests(self, requester):
        return self.db.query(ApprovalRequest).filter_by(
            requester_user_id=requester.user_id,
        ).order_by(ApprovalRequest.created_at.desc()).all()

    def list_review(self, approver, request_type=None, status=None, requester_user_id=None, project_id=None):
        query = self.db.query(ApprovalRequest)
        if approver.role != UserRole.admin:
            query = query.filter_by(approver_user_id=approver.user_id)
        if request_type:
            query = query.filter_by(request_type=request_type)
        if status:
            query = query.filter_by(status=status)
        if requester_user_id:
            query = query.filter_by(requester_user_id=requester_user_id)
        if project_id:
            query = query.filter(
                ApprovalRequest.request_type.in_({'api_key', 'project_access'}),
                ApprovalRequest.target_id == project_id,
            )
        return query.order_by(ApprovalRequest.created_at.asc()).all()

    def list_pending(self, approver):
        return self.list_review(approver, status='pending')

    def cancel(self, requester, request_id):
        request = self.db.query(ApprovalRequest).filter_by(request_id=request_id).with_for_update().first()
        if request is None:
            raise HTTPException(404, '审批申请不存在')
        if request.requester_user_id != requester.user_id:
            raise HTTPException(403, '只能撤回自己的申请')
        if request.status != 'pending':
            raise HTTPException(409, '只有待审批申请可以撤回')
        request.status = 'cancelled'
        request.decided_at = datetime.utcnow()
        self.db.add(OperationLog(
            log_id=f'log_{secrets.token_hex(12)}', operator_id=requester.user_id,
            operator_name=requester.username, action='approval_cancelled',
            target_type='approval_request', target_id=request.request_id,
            detail=json.dumps({'request_type': request.request_type, 'status': 'cancelled'}, ensure_ascii=False),
        ))
        self.db.commit()
        self.db.refresh(request)
        return request

    def decide(self, approver, request_id, decision, comment=None):
        if decision not in {'approved', 'rejected'}:
            raise HTTPException(422, '审批结果必须是 approved 或 rejected')
        request = self.db.query(ApprovalRequest).filter_by(
            request_id=request_id,
        ).populate_existing().with_for_update().first()
        if request is None:
            raise HTTPException(404, '审批申请不存在')
        if request.status != 'pending':
            raise HTTPException(409, '该审批申请已处理')
        if request.requester_user_id == approver.user_id:
            raise HTTPException(403, '不能审批自己的申请')
        if approver.role != UserRole.admin and request.approver_user_id != approver.user_id:
            raise HTTPException(403, '无权审批该申请')

        try:
            if decision == 'approved':
                action = self.actions.get(request.request_type)
                if action is None:
                    raise HTTPException(501, '该类型的审批生效动作尚未配置')
                action(self.db, request)

            request.status = decision
            request.approver_user_id = approver.user_id
            request.decision_comment = comment
            request.decided_at = datetime.utcnow()
            self.db.add(OperationLog(
                log_id=f'log_{secrets.token_hex(12)}', operator_id=approver.user_id,
                operator_name=approver.username, action=f'approval_{decision}',
                target_type='approval_request', target_id=request.request_id,
                detail=json.dumps({'request_type': request.request_type, 'status': decision,
                                   'decision_comment': comment}, ensure_ascii=False),
            ))
            self.db.commit()
            self.db.refresh(request)
            self._notify_requester(request)
            return request
        except BaseException:
            self.db.rollback()
            raise

    def _notify_requester(self, request):
        try:
            user = self.db.query(User).filter_by(user_id=request.requester_user_id).first()
            if user is None:
                return
            result = '通过' if request.status == 'approved' else '拒绝'
            amount = request.payload.get('amount', 0)
            titles = {
                'quota': '额度申请', 'api_key': 'API Key 申请',
                'model_group': '模型分组申请', 'project_access': '项目权限申请',
            }
            title = titles[request.request_type]
            detail = (f'您的 {amount} tokens 额度申请已{result}。' if request.request_type == 'quota'
                      else f'您的 {title}已{result}。')
            notice = Notification(
                notif_id=f'notif_{secrets.token_hex(8)}', user_id=user.user_id,
                type=NotificationType.approval_result, title=f'{title}已{result}',
                content=f'{detail}申请单：{request.request_id}'
                       + (f'；审批意见：{request.decision_comment}' if request.decision_comment else ''),
                extra_data=json.dumps({'request_id': request.request_id, 'status': request.status}),
                is_read=0,
            )
            self.db.add(notice)
            self.db.commit()
        except Exception:
            logger.exception('额度申请结果通知保存失败: {}', request.request_id)
            self.db.rollback()
