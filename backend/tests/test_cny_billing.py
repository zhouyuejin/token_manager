"""人民币快照不会随汇率或模型价格改变。"""
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.system_config import SystemConfig
from app.services.quota_reservation_service import cost


def test_cost_converts_before_rounding_and_keeps_snapshot():
    row = SimpleNamespace(price_type='token', input_price=Decimal('0.000001'),
                          output_price=Decimal('0.0012'), request_price=0,
                          price_currency='USD', exchange_rate=Decimal('7.12345678'))
    assert cost(row, {'prompt_tokens': 1}) == Decimal('0.00000001')
    assert cost(row, {'completion_tokens': 388}) == Decimal('0.00331669')
    row.price_currency = 'CNY'
    assert cost(row, {'completion_tokens': 388}) == Decimal('0.00046560')


def test_request_price_uses_frozen_exchange_rate():
    row = SimpleNamespace(price_type='request', request_price=Decimal('0.01'),
                          price_currency='USD', exchange_rate=Decimal('7.1'))
    assert cost(row, {}) == Decimal('0.07100000')


def test_rate_cache_rejects_invalid_or_older_rates_and_survives_restart(monkeypatch):
    from app.services import exchange_rate_service as fx
    engine = create_engine('sqlite://')
    SystemConfig.__table__.create(engine)
    with Session(engine) as db:
        db.add(SystemConfig(id=1, config_key=fx.RATE_KEY))
        db.commit()
        saved = fx.save_rate(db, {'base': 'USD', 'quote': 'CNY', 'date': '2026-10-08', 'rate': '7.1'})
        assert saved['rate'] == '7.10000000'
        fx.save_rate(db, {'base': 'USD', 'quote': 'CNY', 'date': '2026-10-07', 'rate': '8'})
        assert fx.get_rate(db)['rate'] == '7.10000000'
        for value in ['0', '-1', 'NaN', 'Infinity']:
            with pytest.raises(ValueError):
                fx.save_rate(db, {'base': 'USD', 'quote': 'CNY', 'date': '2026-10-08', 'rate': value})
    with Session(engine) as db:
        monkeypatch.setattr(fx, 'fetch_rate', lambda **kw: (_ for _ in ()).throw(OSError('offline')))
        assert fx.refresh_rate(db)['rate'] == '7.10000000'
        assert fx.rate_status(db)['stale'] is True


def test_usd_without_cache_fails_but_cny_needs_no_rate():
    from app.services import exchange_rate_service as fx
    engine = create_engine('sqlite://')
    SystemConfig.__table__.create(engine)
    with Session(engine) as db:
        assert fx.price_snapshot(db, 'CNY')['exchange_rate'] == Decimal('1')
        with pytest.raises(HTTPException) as exc:
            fx.price_snapshot(db, 'USD')
        assert exc.value.status_code == 503


def test_historical_rate_uses_previous_available_day(monkeypatch):
    from app.services import exchange_rate_service as fx
    payload = {'base': 'USD', 'quote': 'CNY', 'date': '2026-10-02', 'rate': '7.1'}
    class Response:
        def raise_for_status(self): pass
        def json(self): return payload
    monkeypatch.setattr(fx.httpx, 'get', lambda *a, **kw: Response())
    assert fx.fetch_rate(on_date=date(2026, 10, 4))['date'] == '2026-10-02'
    payload['date'] = '2026-10-05'
    with pytest.raises(ValueError):
        fx.fetch_rate(on_date=date(2026, 10, 4))


def test_reservation_and_usage_share_fx_after_rate_changes(db):
    from app.models.user import User
    from app.models.api_key import ApiKey
    from app.models.model import Model
    from app.models.quota_reservation import QuotaReservation
    from app.models.usage_log import UsageLog
    from app.services.exchange_rate_service import save_rate
    from app.services.quota_reservation_service import QuotaReservationService
    from app.services.proxy_service import ProxyService
    db.add_all([User(user_id='fx-user', username='fx-user', email='fx@test', password='hash', quota=-1),
                ApiKey(key_id='fx-key', user_id='fx-user', api_key='fx-key', key_name='fx'),
                Model(model_id='fx-model', price_currency='USD', price_per_1k_input=0,
                      price_per_1k_output=Decimal('0.0012'))])
    db.commit()
    save_rate(db, {'base': 'USD', 'quote': 'CNY', 'date': date.today().isoformat(), 'rate': '7.1'})
    service = QuotaReservationService(db)
    def reserve():
        return service.reserve(db.query(User).filter_by(user_id='fx-user').one(), db.query(ApiKey).filter_by(key_id='fx-key').one(), 'fx-model',
                               {'messages': [], 'max_tokens': 100}, {'project_id': None, 'department_id': None})
    first = reserve()
    save_rate(db, {'base': 'USD', 'quote': 'CNY', 'date': date.today().isoformat(), 'rate': '8'})
    db.query(Model).filter_by(model_id='fx-model').update({'price_per_1k_output': Decimal('0.003')})
    db.commit()
    tokens = {'prompt_tokens': 0, 'completion_tokens': 80, 'total_tokens': 80}
    service.commit(first, tokens)
    proxy = ProxyService(db)
    proxy.reservation_id = first
    proxy.record_usage('fx-user', 'fx-key', None, 'fx-model', tokens, 1, 200)
    db.commit()
    row = db.get(QuotaReservation, first)
    assert row.actual_cost_cny == Decimal('0.00068160')
    log = db.query(UsageLog).one()
    assert log.cost_cny == row.actual_cost_cny
    assert log.exchange_rate == row.exchange_rate == Decimal('7.1')
    second = reserve()
    service.commit(second, tokens)
    assert db.get(QuotaReservation, second).actual_cost_cny == Decimal('0.00192000')
    assert row.actual_cost_cny == Decimal('0.00068160')
    assert row.actual_cost_usd is None  # Never store CNY in old audit columns.


def test_legacy_migration_preserves_usd_and_is_idempotent(db):
    from app.models.usage_log import UsageLog
    from app.models.budget import Budget
    from app.scripts.migrate_cny_billing import migrate
    db.add(UsageLog(log_id='old-fx', user_id='old-user', model='old-model', status_code=200,
                    cost_usd=Decimal('0.02'), created_at=datetime(2026, 10, 4)))
    # CNY is explicitly absent for pre-switch records, and added by the schema migration.
    from sqlalchemy import text
    db.execute(text("INSERT INTO budgets (budget_id, scope_type, scope_id, month, amount_usd, thresholds, policy, enabled) VALUES ('old-budget', 'project', 'p', '2026-10', 10, '[80]', 'block', 1)"))
    db.commit()
    def historical_rate(*, on_date):
        return {'rate': '7.1', 'date': on_date.isoformat(), 'source': 'test'}
    assert migrate(db, historical_rate)['usages'] == 1
    log = db.query(UsageLog).one()
    assert log.cost_cny == Decimal('0.14200000')
    assert log.cost_usd == Decimal('0.02')
    assert log.conversion_kind == 'legacy_historical_conversion'
    budget = db.get(Budget, 'old-budget')
    assert budget.amount_cny == Decimal('71') and budget.amount_usd == Decimal('10')
    assert migrate(db, lambda **kw: (_ for _ in ()).throw(AssertionError('must not fetch again'))) == {
        'reservations': 0, 'usages': 0, 'budgets': 0}


def test_native_price_precision_survives_database_roundtrip(db):
    from app.models.model import Model
    price = Decimal('0.000007123457')
    db.add(Model(model_id='tiny-cny', price_currency='CNY', price_per_1k_input=price))
    db.commit()
    db.expire_all()
    assert db.query(Model).filter_by(model_id='tiny-cny').one().price_per_1k_input == price
