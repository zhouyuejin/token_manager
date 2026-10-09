"""Latest published USD/CNY reference rate, persisted separately from request snapshots."""
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import httpx
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.system_config import SystemConfig

RATE_KEY = 'usd_cny_exchange_rate'
SOURCE = 'Frankfurter'
URL = 'https://api.frankfurter.dev/v2/rate/USD/CNY'
logger = logging.getLogger(__name__)


def validate_rate(payload, on_date=None):
    try:
        value = Decimal(str(payload['rate']))
        published = date.fromisoformat(payload['date'])
        if (payload['base'] != 'USD' or payload['quote'] != 'CNY'
                or not value.is_finite() or value <= 0 or value >= 1000
                or published > (on_date or date.today())):
            raise ValueError('Invalid USD/CNY rate')
        value = value.quantize(Decimal('0.00000001'))
        if not value:
            raise ValueError('Rate below precision')
    except (KeyError, InvalidOperation, TypeError) as exc:
        raise ValueError('Invalid USD/CNY response') from exc
    return {'rate': str(value), 'date': published.isoformat(), 'source': SOURCE}


def fetch_rate(*, on_date=None):
    response = httpx.get(URL, params={'date': on_date.isoformat()} if on_date else None, timeout=10)
    response.raise_for_status()
    return validate_rate(response.json(), on_date)


def get_rate(db):
    row = db.query(SystemConfig).filter_by(config_key=RATE_KEY).populate_existing().first()
    return json.loads(row.config_value) if row and row.config_value else None


def save_rate(db, payload):
    value = validate_rate(payload)
    row = db.query(SystemConfig).filter_by(config_key=RATE_KEY).populate_existing().with_for_update().first()
    old = json.loads(row.config_value) if row and row.config_value else None
    if old and old['date'] > value['date']:
        db.rollback()
        return old
    value.update(fetched_at=datetime.utcnow().isoformat(), refresh_failed=False)
    if row is None:
        row = SystemConfig(config_key=RATE_KEY, description='Latest published USD/CNY reference rate')
        db.add(row)
    row.config_value = json.dumps(value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        current = get_rate(db)
        if current is None:
            raise
        return current
    return value


def refresh_rate(db):
    try:
        value = fetch_rate()
        return save_rate(db, {**value, 'base': 'USD', 'quote': 'CNY'})
    except Exception:
        db.rollback()
        logger.warning('汇率更新失败，保留最近成功汇率', exc_info=True)
        row = db.query(SystemConfig).filter_by(config_key=RATE_KEY).with_for_update().first()
        if row and row.config_value:
            value = json.loads(row.config_value)
            value['refresh_failed'] = True
            row.config_value = json.dumps(value)
            db.commit()
            return value
        return None


def rate_status(db):
    value = get_rate(db)
    if not value:
        return {'available': False, 'stale': True, 'source': SOURCE, 'frequency': 'daily'}
    stale = value.get('refresh_failed', False) or datetime.fromisoformat(value['fetched_at']) < datetime.utcnow() - timedelta(hours=2)
    return {**value, 'available': True, 'stale': stale, 'frequency': 'daily'}


def price_snapshot(db, currency):
    if currency == 'CNY':
        return {'price_currency': 'CNY', 'exchange_rate': Decimal('1'),
                'exchange_rate_date': None, 'exchange_rate_source': 'CNY', 'conversion_kind': 'native_cny'}
    if currency != 'USD':
        raise ValueError('Unsupported price currency')
    value = get_rate(db)
    if not value:
        raise HTTPException(503, '尚无有效 USD/CNY 汇率，请等待汇率同步后重试')
    return {'price_currency': 'USD', 'exchange_rate': Decimal(value['rate']),
            'exchange_rate_date': date.fromisoformat(value['date']),
            'exchange_rate_source': value['source'], 'conversion_kind': 'request_snapshot'}


def model_prices_cny(db, model):
    snapshot = price_snapshot(db, model.price_currency)
    return {**{field: (Decimal(getattr(model, field) or 0) * snapshot['exchange_rate']).quantize(Decimal('0.000000000001')) for field in
               ('price_per_1k_input', 'price_per_1k_output', 'price_per_request')},
            'price_currency': 'CNY', 'source_price_currency': model.price_currency}
