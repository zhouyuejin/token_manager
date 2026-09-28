import pytest
from fastapi import HTTPException

from app.models.operation_log import OperationLog
from app.models.notification import Notification, NotificationType
from app.models.quota_record import QuotaRecord, QuotaRecordType
from app.models.user import User, UserRole
from app.services.approval_service import ApprovalService
from app.services.quota_approval_service import apply_quota_approval
from app.schemas.approval import QuotaApplicationCreate


def add_user(db, user_id, role=UserRole.user):
    user = User(user_id=user_id, username=user_id, email=f'{user_id}@test', password='hash', role=role)
    db.add(user)
    db.commit()
    return user


def test_create_and_list_approval_requests(db):
    requester = add_user(db, 'requester')
    approver = add_user(db, 'approver')
    service = ApprovalService(db)

    request = service.create_request(
        requester, 'quota', {'amount': 100}, reason='需要测试额度', approver_user_id=approver.user_id,
    )

    assert request.status == 'pending'
    assert request.payload == {'amount': 100}
    assert service.list_my_requests(requester) == [request]
    assert service.list_pending(approver) == [request]


def test_approval_decision_applies_action_and_writes_operation_log(db):
    requester = add_user(db, 'requester')
    approver = add_user(db, 'approver', UserRole.admin)
    applied = []
    service = ApprovalService(db, actions={'quota': lambda db, request: applied.append(request.request_id)})
    request = service.create_request(requester, 'quota', {'amount': 100}, reason='额度申请')

    decided = service.decide(approver, request.request_id, 'approved', '同意')

    assert decided.status == 'approved'
    assert decided.approver_user_id == approver.user_id
    assert applied == [request.request_id]
    log = db.query(OperationLog).filter_by(target_type='approval_request', target_id=request.request_id).one()
    assert log.action == 'approval_approved'
    assert log.operator_id == approver.user_id


def test_reject_does_not_apply_action_and_cannot_be_decided_twice(db):
    requester = add_user(db, 'requester')
    approver = add_user(db, 'approver', UserRole.admin)
    applied = []
    service = ApprovalService(db, actions={'quota': lambda db, request: applied.append(request.request_id)})
    request = service.create_request(requester, 'quota', {'amount': 100}, reason='额度申请')

    service.decide(approver, request.request_id, 'rejected', '信息不足')

    assert applied == []
    with pytest.raises(HTTPException) as error:
        service.decide(approver, request.request_id, 'approved')
    assert error.value.status_code == 409
    assert '已处理' in error.value.detail


def test_requester_cannot_approve_own_request(db):
    requester = add_user(db, 'requester', UserRole.admin)
    service = ApprovalService(db, actions={'quota': lambda db, request: None})
    request = service.create_request(requester, 'quota', {'amount': 100}, reason='额度申请')

    with pytest.raises(HTTPException) as error:
        service.decide(requester, request.request_id, 'approved')

    assert error.value.status_code == 403
    assert '不能审批自己的申请' in error.value.detail
    assert request.status == 'pending'


def test_non_admin_cannot_decide_request_assigned_to_another_approver(db):
    requester = add_user(db, 'requester')
    approver = add_user(db, 'approver')
    other = add_user(db, 'other')
    service = ApprovalService(db, actions={'quota': lambda db, request: None})
    request = service.create_request(
        requester, 'quota', {'amount': 100}, reason='额度申请', approver_user_id=approver.user_id,
    )

    with pytest.raises(HTTPException) as error:
        service.decide(other, request.request_id, 'rejected')

    assert error.value.status_code == 403
    assert request.status == 'pending'


def test_approval_without_domain_action_is_rejected_without_changing_status(db):
    requester = add_user(db, 'requester')
    approver = add_user(db, 'approver', UserRole.admin)
    request = ApprovalService(db).create_request(requester, 'quota', {'amount': 100}, reason='额度申请')

    with pytest.raises(HTTPException) as error:
        ApprovalService(db).decide(approver, request.request_id, 'approved')

    assert error.value.status_code == 501
    assert '生效动作尚未配置' in error.value.detail
    assert request.status == 'pending'


def test_quota_approval_increases_balance_and_links_ledger_to_request(db):
    requester = add_user(db, 'quota_requester')
    requester.quota = 100
    approver = add_user(db, 'quota_approver', UserRole.admin)
    request = ApprovalService(db).create_request(
        requester, 'quota', {'amount': 50}, reason='项目测试',
    )

    ApprovalService(db, actions={'quota': apply_quota_approval}).decide(
        approver, request.request_id, 'approved', '同意',
    )

    assert db.query(User).filter_by(user_id=requester.user_id).one().quota == 150
    record = db.query(QuotaRecord).one()
    assert record.type == QuotaRecordType.increase
    assert record.amount == 50
    assert record.source == 'approval'
    assert request.request_id in record.reason


def test_rejected_quota_application_notifies_requester_without_changing_quota(db):
    requester = add_user(db, 'quota_rejected')
    requester.quota = 100
    approver = add_user(db, 'quota_rejector', UserRole.admin)
    request = ApprovalService(db).create_request(
        requester, 'quota', {'amount': 50}, reason='项目测试',
    )

    ApprovalService(db, actions={'quota': apply_quota_approval}).decide(
        approver, request.request_id, 'rejected', '理由不足',
    )

    assert db.query(User).filter_by(user_id=requester.user_id).one().quota == 100
    assert db.query(QuotaRecord).count() == 0
    notice = db.query(Notification).filter_by(user_id=requester.user_id).one()
    assert notice.type == NotificationType.approval_result
    assert request.request_id in notice.content


def test_quota_approval_notifies_requester(db):
    requester = add_user(db, 'quota_approved')
    requester.quota = 100
    approver = add_user(db, 'quota_approver_admin', UserRole.admin)
    request = ApprovalService(db).create_request(
        requester, 'quota', {'amount': 25}, reason='项目测试',
    )

    ApprovalService(db, actions={'quota': apply_quota_approval}).decide(
        approver, request.request_id, 'approved', '同意',
    )

    notice = db.query(Notification).filter_by(user_id=requester.user_id).one()
    assert notice.type == NotificationType.approval_result
    assert '通过' in notice.content
    assert request.request_id in notice.content


@pytest.mark.parametrize('amount', [0, -1, True])
def test_quota_application_rejects_non_positive_or_boolean_amount(amount):
    with pytest.raises(Exception):
        QuotaApplicationCreate(amount=amount, reason='需要额度')


def test_quota_application_rejects_blank_reason():
    with pytest.raises(Exception):
        QuotaApplicationCreate(amount=1, reason='   ')
