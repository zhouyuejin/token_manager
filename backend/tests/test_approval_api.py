import pytest
from fastapi import HTTPException

from app.api.v1 import approvals
from app.models.approval import ApprovalRequest
from app.models.notification import Notification, NotificationType
from app.models.model_group import ModelGroup, ModelGroupStatus
from app.models.organization import Department
from app.models.project import Project, UserProject
from app.models.user import User, UserRole
from app.schemas.approval import ApprovalDecision, ProjectAccessApplicationCreate


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
        {'user_id': another_requester.user_id, 'username': another_requester.username},
        {'user_id': requester.user_id, 'username': requester.username},
    ]
    assert len(approvals.list_review_requesters(db, admin)) == 2

    cancelled = approvals.cancel_my_application(first.request_id, db, requester)
    assert cancelled.status == 'cancelled'
    with pytest.raises(HTTPException) as error:
        approvals.cancel_my_application(second.request_id, db, other)
    assert error.value.status_code == 403
    assert second.status == 'pending'


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
