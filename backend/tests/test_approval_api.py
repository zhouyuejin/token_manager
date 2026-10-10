import json

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.api.v1 import approvals
from app.core.database import get_db
from app.dependencies import get_current_user
from app.models.api_key import ApiKey
from app.models.approval import ApprovalRequest
from app.models.notification import Notification, NotificationType
from app.models.operation_log import OperationLog
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.organization import Department
from app.models.project import Project, UserProject
from app.models.user import User, UserRole
from app.schemas.approval import ApprovalDecision, ApprovalSupplement, ProjectAccessApplicationCreate


def add_user(db, user_id, role=UserRole.user):
    user = User(user_id=user_id, username=user_id, email=f'{user_id}@test', password='hash', role=role)
    db.add(user)
    db.commit()
    return user


def add_project(db, project_id, owner_user_id):
    db.add(Department(dept_id=f'dept_{project_id}', name='部门'))
    project = Project(project_id=project_id, dept_id=f'dept_{project_id}', name=project_id,
                      owner_user_id=owner_user_id, status='active')
    db.add(project)
    db.commit()
    return project


def test_project_access_request_is_granted_by_project_owner(db):
    requester = add_user(db, 'requester')
    owner = add_user(db, 'owner')
    add_project(db, 'project_one', owner.user_id)

    request = approvals.create_project_access_application(
        ProjectAccessApplicationCreate(project_id='project_one', reason='需要访问项目'), db, requester,
    )

    assert request.status == 'pending'
    assert request.approver_user_id == owner.user_id
    assert db.query(UserProject).filter_by(user_id=requester.user_id, project_id='project_one').first() is None

    decided = approvals.decide_application(
        request.request_id, ApprovalDecision(decision='approved', comment='已确认'), db, owner,
    )

    assert decided.status == 'approved'
    assert db.query(UserProject).filter_by(user_id=requester.user_id, project_id='project_one').one()
    assert db.query(Notification).filter_by(
        user_id=requester.user_id, type=NotificationType.approval_result,
    ).count() == 1


def test_project_access_options_exclude_members_and_disabled_projects(db):
    requester = add_user(db, 'requester')
    owner = add_user(db, 'owner')
    add_project(db, 'available', owner.user_id)
    member_project = add_project(db, 'member_project', owner.user_id)
    disabled = add_project(db, 'disabled', owner.user_id)
    disabled.status = 'disabled'
    db.add_all([
        UserProject(user_id=requester.user_id, project_id=member_project.project_id),
    ])
    db.commit()

    options = approvals.list_project_access_options(db, requester)

    assert [item['project_id'] for item in options] == ['available']


def test_disabled_project_access_application_cannot_be_approved(db):
    requester = add_user(db, 'requester')
    owner = add_user(db, 'owner')
    project = add_project(db, 'project_one', owner.user_id)
    request = approvals.create_project_access_application(
        ProjectAccessApplicationCreate(project_id=project.project_id, reason='需要访问项目'), db, requester,
    )
    project.status = 'disabled'
    db.commit()

    with pytest.raises(HTTPException) as error:
        approvals.decide_application(
            request.request_id, ApprovalDecision(decision='approved', comment='同意'), db, owner,
        )

    assert error.value.status_code == 409
    assert request.status == 'pending'
    assert db.query(UserProject).filter_by(user_id=requester.user_id, project_id=project.project_id).first() is None


def test_project_access_rejects_duplicate_pending_and_existing_membership(db):
    requester = add_user(db, 'requester')
    owner = add_user(db, 'owner')
    project = add_project(db, 'project_one', owner.user_id)
    data = ProjectAccessApplicationCreate(project_id=project.project_id, reason='需要访问项目')
    first = approvals.create_project_access_application(data, db, requester)

    with pytest.raises(HTTPException) as duplicate:
        approvals.create_project_access_application(data, db, requester)
    assert duplicate.value.status_code == 409
    assert db.query(ApprovalRequest).filter_by(requester_user_id=requester.user_id).count() == 1

    approvals.cancel_my_application(first.request_id, db, requester)
    db.add(UserProject(user_id=requester.user_id, project_id=project.project_id))
    db.commit()
    with pytest.raises(HTTPException) as already_member:
        approvals.create_project_access_application(data, db, requester)
    assert already_member.value.status_code == 409


def test_model_group_options_exclude_granted_and_disabled_groups(db):
    user = add_user(db, 'requester')
    user.model_group_ids = '["already_granted"]'
    db.add_all([
        ModelGroup(group_id='already_granted', name='已有', status=ModelGroupStatus.active),
        ModelGroup(group_id='available', name='可申请', status=ModelGroupStatus.active),
        ModelGroup(group_id='disabled', name='停用', status=ModelGroupStatus.disabled),
    ])
    db.commit()

    options = approvals.list_model_group_application_options(db, user)

    assert options == [{'group_id': 'available', 'name': '可申请'}]


def test_reviewer_scope_filters_and_requester_can_cancel(db):
    requester = add_user(db, 'requester')
    another_requester = add_user(db, 'another_requester')
    owner = add_user(db, 'owner')
    other = add_user(db, 'other')
    admin = add_user(db, 'admin', UserRole.admin)
    add_project(db, 'project_one', owner.user_id)
    first = approvals.create_project_access_application(
        ProjectAccessApplicationCreate(project_id='project_one', reason='申请一'), db, requester,
    )
    second = approvals._service(db).create_request(
        another_requester, 'quota', {'amount': 100}, '申请二', approver_user_id=owner.user_id,
    )

    owner_requests = approvals.list_review_applications(db, owner, status='pending', project_id='project_one')
    assert [request['request_id'] for request in owner_requests] == [first.request_id]
    assert approvals.list_review_applications(db, other) == []
    assert len(approvals.list_review_applications(db, admin, requester_user_id=requester.user_id)) == 1
    assert approvals.list_review_requesters(db, owner) == [
        {'user_id': another_requester.user_id, 'username': another_requester.username, 'nickname': None},
        {'user_id': requester.user_id, 'username': requester.username, 'nickname': None},
    ]
    assert len(approvals.list_review_requesters(db, admin)) == 2

    cancelled = approvals.cancel_my_application(first.request_id, db, requester)
    assert cancelled.status == 'cancelled'
    assert db.query(Notification).filter_by(user_id=owner.user_id, type=NotificationType.approval_update).count() == 3
    assert db.query(OperationLog).filter_by(target_id=first.request_id, action='approval_cancelled').count() == 1
    with pytest.raises(HTTPException) as error:
        approvals.cancel_my_application(second.request_id, db, other)
    assert error.value.status_code == 403
    assert second.status == 'pending'


def test_supplement_round_trip_and_permissions(db):
    requester = add_user(db, 'requester')
    owner = add_user(db, 'owner')
    other = add_user(db, 'other')
    add_project(db, 'project_one', owner.user_id)
    request = approvals.create_project_access_application(
        ProjectAccessApplicationCreate(project_id='project_one', reason='需要项目权限'), db, requester,
    )

    with pytest.raises(HTTPException) as blank_comment:
        approvals._service(db).decide(owner, request.request_id, 'approved', '   ')
    assert blank_comment.value.status_code == 422
    assert request.status == 'pending'

    approvals.decide_application(
        request.request_id, ApprovalDecision(decision='needs_info', comment='说明用途'), db, owner,
    )
    assert request.status == 'needs_info'
    assert db.query(UserProject).filter_by(user_id=requester.user_id, project_id='project_one').count() == 0
    assert db.query(Notification).filter_by(user_id=requester.user_id, type=NotificationType.approval_update).count() == 1

    with pytest.raises(HTTPException) as unauthorized:
        approvals.supplement_my_application(request.request_id, ApprovalSupplement(content='接口联调'), db, other)
    assert unauthorized.value.status_code == 403
    with pytest.raises(HTTPException) as duplicate_decision:
        approvals.decide_application(
            request.request_id, ApprovalDecision(decision='approved', comment='同意'), db, owner,
        )
    assert duplicate_decision.value.status_code == 409

    approvals.supplement_my_application(
        request.request_id, ApprovalSupplement(content='用于接口联调'), db, requester,
    )
    assert request.status == 'pending'
    assert request.supplement == '用于接口联调'
    assert len(approvals.list_review_applications(db, owner, status='pending')) == 1
    assert db.query(Notification).filter_by(user_id=owner.user_id, type=NotificationType.approval_update).count() == 2
    assert db.query(OperationLog).filter_by(target_id=request.request_id).count() == 3

    approvals.decide_application(
        request.request_id, ApprovalDecision(decision='approved', comment='同意'), db, owner,
    )
    assert request.status == 'approved'
    assert db.query(UserProject).filter_by(user_id=requester.user_id, project_id='project_one').count() == 1


def test_needs_info_application_can_be_cancelled(db):
    requester = add_user(db, 'requester')
    owner = add_user(db, 'owner')
    add_project(db, 'project_one', owner.user_id)
    request = approvals.create_project_access_application(
        ProjectAccessApplicationCreate(project_id='project_one', reason='需要项目权限'), db, requester,
    )
    approvals.decide_application(
        request.request_id, ApprovalDecision(decision='needs_info', comment='请补充'), db, owner,
    )
    approvals.cancel_my_application(request.request_id, db, requester)
    assert request.status == 'cancelled'
    assert db.query(Notification).filter_by(user_id=owner.user_id, type=NotificationType.approval_update).count() == 2


def test_approval_comments_and_supplements_require_text():
    with pytest.raises(Exception):
        ApprovalDecision(decision='approved', comment='   ')
    with pytest.raises(Exception):
        ApprovalSupplement(content='   ')


def test_reviewer_history_never_returns_api_key_plaintext(db):
    requester = add_user(db, 'requester')
    admin = add_user(db, 'admin', UserRole.admin)
    request = ApprovalRequest(
        request_id='approved_key', request_type='api_key', requester_user_id=requester.user_id,
        payload={'project_id': 'project_one', 'result': {'api_key': 'sk-secret-once'}},
        status='approved', reason='需要 API Key',
    )
    db.add(request)
    db.commit()

    result = approvals.list_review_applications(db, admin, status='approved')

    assert result[0]['payload'] == {'project_id': 'project_one'}
    assert 'result' not in result[0]


def test_claim_key_is_owner_only_and_isolates_multiple_applications(db):
    requester = add_user(db, 'requester')
    other = add_user(db, 'other')
    admin = add_user(db, 'admin', UserRole.admin)
    for request_id in ['key_one', 'key_two']:
        db.add(ApprovalRequest(
            request_id=request_id, request_type='api_key', requester_user_id=requester.user_id,
            payload={'result': {'key_id': request_id, 'api_key': f'secret-{request_id}'}},
            status='approved', reason='调用',
        ))
    db.commit()

    assert all(item['secret_available'] for item in approvals.list_my_applications(db, requester))
    assert approvals.list_my_applications(db, other) == []
    for user in [other, admin]:
        with pytest.raises(HTTPException) as error:
            approvals.claim_api_key('key_one', db, user)
        assert error.value.status_code == 403
    assert approvals.claim_api_key('key_one', db, requester)['api_key'] == 'secret-key_one'
    available = {item['request_id']: item['secret_available'] for item in approvals.list_my_applications(db, requester)}
    assert available == {'key_one': False, 'key_two': True}
    assert approvals.claim_api_key('key_two', db, requester)['api_key'] == 'secret-key_two'


@pytest.mark.parametrize('request_type,status', [('quota', 'approved'), ('api_key', 'pending'), ('api_key', 'rejected')])
def test_claim_key_requires_approved_key_application(db, request_type, status):
    requester = add_user(db, 'requester')
    db.add(ApprovalRequest(request_id='invalid', request_type=request_type,
                           requester_user_id=requester.user_id, status=status, reason='理由', payload={}))
    db.commit()
    with pytest.raises(HTTPException) as error:
        approvals.claim_api_key('invalid', db, requester)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as missing:
        approvals.claim_api_key('missing', db, requester)
    assert missing.value.status_code == 404


def test_concurrent_key_claims_only_return_plaintext_once(db, SessionLocal):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    requester = add_user(db, 'requester')
    db.add(ApprovalRequest(
        request_id='concurrent_key', request_type='api_key', requester_user_id=requester.user_id,
        payload={'result': {'key_id': 'key_one', 'api_key': 'secret-once'}}, status='approved', reason='调用',
    ))
    db.commit()
    barrier = Barrier(2)

    def claim():
        with SessionLocal() as session:
            user = session.query(User).filter_by(user_id='requester').one()
            barrier.wait(timeout=10)
            try:
                return approvals.claim_api_key('concurrent_key', session, user)
            except HTTPException as error:
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert results.count(409) == 1
    assert {'key_id': 'key_one', 'api_key': 'secret-once'} in results
    assert db.query(OperationLog).filter_by(target_id='concurrent_key', action='approval_key_claimed').count() == 1


def test_approval_http_flow_applies_all_request_types_and_limits_key_reveal(db):
    requester = add_user(db, 'requester')
    owner = add_user(db, 'owner')
    admin = add_user(db, 'admin', UserRole.admin)
    requester.quota = 10
    add_project(db, 'key_project', owner.user_id)
    add_project(db, 'join_project', owner.user_id)
    db.add(UserProject(user_id=requester.user_id, project_id='key_project'))
    db.add(ModelGroup(group_id='group_one', name='可用分组', status=ModelGroupStatus.active))
    db.commit()

    app = FastAPI()
    app.include_router(approvals.router, prefix='/approvals')
    app.dependency_overrides[get_db] = lambda: db

    def current_user(request: Request):
        return db.query(User).filter_by(user_id=request.headers['x-user-id']).one()

    app.dependency_overrides[get_current_user] = current_user
    client = TestClient(app)

    def post(path, user, data):
        response = client.post(path, json=data, headers={'x-user-id': user.user_id})
        assert response.status_code == 200, response.text
        return response.json()

    key_request = post('/approvals/api-key', requester, {
        'project_id': 'key_project', 'name': '联调', 'reason': '接口联调',
    })
    assert db.query(ApiKey).count() == 0
    key_decision = post(f"/approvals/{key_request['request_id']}/decision", owner,
                        {'decision': 'approved', 'comment': '同意'})
    key = db.query(ApiKey).one()
    assert key.api_key not in json.dumps(key_decision)
    first = client.get('/approvals/mine', headers={'x-user-id': requester.user_id}).json()
    assert first[0]['secret_available'] is True
    assert key.api_key not in json.dumps(first)
    claimed = post(f"/approvals/{key_request['request_id']}/claim-key", requester, {})
    assert claimed['api_key'] == key.api_key
    second = client.get('/approvals/mine', headers={'x-user-id': requester.user_id}).json()
    assert second[0]['secret_available'] is False
    assert key.api_key not in json.dumps(second)


    quota = post('/approvals/quota', requester, {'amount': 7, 'reason': '需要额度'})
    post(f"/approvals/{quota['request_id']}/decision", admin,
         {'decision': 'approved', 'comment': '同意'})
    db.refresh(requester)
    assert requester.quota == 17

    group = post('/approvals/model-group', requester, {'group_id': 'group_one', 'reason': '需要模型'})
    post(f"/approvals/{group['request_id']}/decision", admin,
         {'decision': 'approved', 'comment': '同意'})
    db.refresh(requester)
    assert 'group_one' in json.loads(requester.model_group_ids)

    project = post('/approvals/project-access', requester,
                   {'project_id': 'join_project', 'reason': '加入项目'})
    post(f"/approvals/{project['request_id']}/decision", owner,
         {'decision': 'approved', 'comment': '同意'})
    assert db.query(UserProject).filter_by(user_id=requester.user_id, project_id='join_project').one()
