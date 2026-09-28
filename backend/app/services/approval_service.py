"""审批申请的创建、查询和单级决策。"""
import json
import secrets
from datetime import datetime

from fastapi import HTTPException

from app.models.approval import ApprovalRequest
from app.models.operation_log import OperationLog
from app.models.user import UserRole


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

    def list_pending(self, approver):
        query = self.db.query(ApprovalRequest).filter_by(status='pending')
        if approver.role != UserRole.admin:
            query = query.filter_by(approver_user_id=approver.user_id)
        return query.order_by(ApprovalRequest.created_at.asc()).all()

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
            return request
        except BaseException:
            self.db.rollback()
            raise
