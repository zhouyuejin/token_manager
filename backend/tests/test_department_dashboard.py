from datetime import datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.api.v1 import projects
from app.core.database import Base, get_db
from app.dependencies import require_admin
from app.models.model import Model
from app.models.organization import Department
from app.models.project import Project
from app.models.usage_log import UsageLog
from app.models.user import User, UserRole


@compiles(BigInteger, 'sqlite')
def sqlite_bigint(element, compiler, **kw):
    return 'INTEGER'


@pytest.fixture
def ctx():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin = User(user_id='dept-admin', username='dept-admin', email='dept@test', password='hash', role=UserRole.department_admin)
    db.add_all([
        admin,
        User(user_id='other-admin', username='other-admin', email='other@test', password='hash', role=UserRole.department_admin),
    ])
    db.commit()
    app = FastAPI()
    app.include_router(projects.router, prefix='/projects')
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_admin] = lambda: admin
    with TestClient(app) as client:
        yield db, client
    db.close()
    engine.dispose()


def add_department(db, dept_id, owner='dept-admin'):
    department = Department(dept_id=dept_id, name=dept_id, owner_user_id=owner, status='active')
    db.add(department)
    db.flush()
    return department


def add_project(db, project_id, dept_id, name=None):
    project = Project(project_id=project_id, dept_id=dept_id, name=name or project_id, status='active')
    db.add(project)
    db.flush()
    return project


def add_log(db, log_id, department_id, project_id, tokens, status=200, at='2026-10-07 12:00:00',
            model='model', cost=None, prompt=0, completion=0):
    db.add(UsageLog(
        log_id=log_id, user_id='user', key_id='key', channel_id='channel', model=model,
        department_id=department_id, project_id=project_id, total_tokens=tokens,
        prompt_tokens=prompt, completion_tokens=completion, status_code=status,
        cost_usd=cost, created_at=datetime.fromisoformat(at),
    ))


def test_usage_stats_aggregate_all_owned_departments_and_costs(ctx):
    db, client = ctx
    add_department(db, 'owned-a')
    add_department(db, 'owned-b')
    add_department(db, 'foreign', owner='other-admin')
    add_project(db, 'project-a', 'owned-a', '项目 A')
    add_project(db, 'project-b', 'owned-b', '项目 B')
    add_project(db, 'foreign-project', 'foreign')
    db.add(Model(model_id='model', price_per_1k_input=Decimal('2'), price_per_1k_output=Decimal('4')))
    db.flush()
    add_log(db, 'saved', 'owned-a', 'project-a', 100, cost=Decimal('0.25'), at='2026-10-07 12:00:00')
    add_log(db, 'legacy', 'owned-b', 'project-b', 50, status=503, prompt=100, completion=50, cost=None, at='2026-10-08 12:00:00')
    add_log(db, 'foreign-log', 'foreign', 'foreign-project', 999, cost=Decimal('9'))
    add_log(db, 'unattributed', None, None, 500, cost=Decimal('5'))
    db.commit()

    response = client.get('/projects/admin/usage-stats', params={'start_date': '2026-10-07', 'end_date': '2026-10-08'})

    assert response.status_code == 200, response.text
    result = response.json()
    assert result['total_tokens'] == 150
    assert result['total_requests'] == 2
    assert result['total_cost'] == pytest.approx(0.65)
    assert result['success_rate'] == 50
    assert result['by_day'] == [
        {'date': '2026-10-07', 'tokens': 100, 'requests': 1},
        {'date': '2026-10-08', 'tokens': 50, 'requests': 1},
    ]
    assert result['by_project'] == [
        {'project_id': 'project-a', 'name': '项目 A', 'tokens': 100, 'requests': 1},
        {'project_id': 'project-b', 'name': '项目 B', 'tokens': 50, 'requests': 1},
    ]


def test_usage_stats_can_filter_to_an_owned_department(ctx):
    db, client = ctx
    add_department(db, 'owned-a')
    add_department(db, 'owned-b')
    add_project(db, 'project-a', 'owned-a')
    add_project(db, 'project-b', 'owned-b')
    add_log(db, 'a', 'owned-a', 'project-a', 10)
    add_log(db, 'b', 'owned-b', 'project-b', 20)
    db.commit()

    result = client.get('/projects/admin/usage-stats', params={
        'start_date': '2026-10-07', 'end_date': '2026-10-08', 'department_id': 'owned-b',
    }).json()

    assert result['total_tokens'] == 20
    assert result['total_requests'] == 1
    assert [row['project_id'] for row in result['by_project']] == ['project-b']


def test_usage_stats_rejects_unowned_department(ctx):
    db, client = ctx
    add_department(db, 'foreign', owner='other-admin')
    db.commit()

    response = client.get('/projects/admin/usage-stats', params={'department_id': 'foreign'})

    assert response.status_code == 404


def test_usage_stats_returns_empty_totals_without_owned_departments(ctx):
    _, client = ctx

    response = client.get('/projects/admin/usage-stats')

    assert response.status_code == 200
    assert response.json() == {
        'total_tokens': 0, 'total_requests': 0, 'total_cost': 0,
        'success_rate': 100, 'by_day': [], 'by_project': [],
        'web_chat': {'tokens': 0, 'requests': 0, 'cost': 0},
    }


def test_usage_stats_apply_inclusive_date_bounds(ctx):
    db, client = ctx
    add_department(db, 'owned')
    add_project(db, 'project', 'owned')
    add_log(db, 'before', 'owned', 'project', 5, at='2026-10-06 23:59:59')
    add_log(db, 'start', 'owned', 'project', 10, at='2026-10-07 00:00:00')
    add_log(db, 'end', 'owned', 'project', 20, at='2026-10-08 23:59:59')
    add_log(db, 'after', 'owned', 'project', 40, at='2026-10-09 00:00:00')
    db.commit()

    response = client.get('/projects/admin/usage-stats', params={'start_date': '2026-10-07', 'end_date': '2026-10-08'})

    assert response.json()['total_tokens'] == 30
    assert response.json()['total_requests'] == 2
