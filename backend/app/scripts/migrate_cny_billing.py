"""One-time, idempotent conversion. Stop API admission and back up the database first.

Run: python -m app.scripts.migrate_cny_billing
Schema must already be upgraded. All USD columns remain unchanged.
"""
import json
from datetime import datetime
from decimal import Decimal, ROUND_CEILING
from types import SimpleNamespace

from app.core.database import SessionLocal
from app.models.budget import Budget
from app.models.model import Model
from app.models.model_channel import ModelChannel
from app.models.quota_reservation import QuotaReservation
from app.models.system_config import SystemConfig
from app.models.usage_log import UsageLog
from app.services.exchange_rate_service import fetch_rate, refresh_rate


def money(amount, rate):
    return (Decimal(amount or 0) * Decimal(rate)).quantize(Decimal('0.00000001'), rounding=ROUND_CEILING)


def migrate(db, historical_rate=fetch_rate):
    if db.query(QuotaReservation).filter_by(status='reserved').count():
        raise RuntimeError('仍有预扣中的请求，请停止准入并等待结算或租约释放后重试')
    reservations = db.query(QuotaReservation).filter(QuotaReservation.estimated_cost_cny.is_(None)).all()
    usages = db.query(UsageLog).filter(UsageLog.cost_cny.is_(None)).all()
    budgets = db.query(Budget).filter(Budget.amount_cny.is_(None)).all()
    config = db.query(SystemConfig).filter_by(config_key='alert_rules').first()
    rules = json.loads(config.config_value) if config and config.config_value else {}
    needs_alert_conversion = 'project_growth_min_cost_usd' in rules and 'project_growth_min_cost_cny' not in rules
    dates = {r.created_at.date() for r in reservations + usages}
    if budgets or needs_alert_conversion:
        dates.add(datetime.utcnow().date())
    # Fetch every required date before touching monetary values. Missing rates fail the whole run.
    rates = {day: historical_rate(on_date=day) for day in sorted(dates)}
    linked = {r.reservation_id: r for r in db.query(QuotaReservation).all()}
    def fields(rate):
        return {'price_currency': 'USD', 'exchange_rate': Decimal(rate['rate']),
                'exchange_rate_date': datetime.fromisoformat(rate['date']),
                'exchange_rate_source': rate['source'], 'conversion_kind': 'legacy_historical_conversion'}
    for row in reservations:
        snapshot = fields(rates[row.created_at.date()])
        for key, value in snapshot.items():
            setattr(row, key, value)
        row.estimated_cost_cny = money(row.estimated_cost_usd, row.exchange_rate)
        row.actual_cost_cny = money(row.actual_cost_usd, row.exchange_rate) if row.actual_cost_usd is not None else None
    models = {m.model_id: m for m in db.query(Model).all()}
    mappings = {(m.channel_id, m.upstream_model): m.model_id for m in db.query(ModelChannel).all()}
    for row in usages:
        reservation = linked.get(row.reservation_id)
        snapshot = ({key: getattr(reservation, key) for key in fields(rates[row.created_at.date()])}
                    if reservation and reservation.exchange_rate is not None else fields(rates[row.created_at.date()]))
        for key, value in snapshot.items():
            setattr(row, key, value)
        if row.cost_usd is not None:
            row.cost_cny = money(row.cost_usd, row.exchange_rate)
        elif row.status_code != 200:
            row.cost_cny = Decimal(0)
        elif reservation and reservation.actual_cost_cny is not None:
            row.cost_cny = reservation.actual_cost_cny
        else:
            model = models.get(row.model) or models.get(mappings.get((row.channel_id, row.model)))
            if not model:
                raise RuntimeError(f'历史日志 {row.log_id} 缺少费用且无法定位价格，请人工核对')
            from app.services.quota_reservation_service import cost
            row.cost_cny = cost(SimpleNamespace(price_type=getattr(model.price_type, 'value', model.price_type),
                input_price=model.price_per_1k_input, output_price=model.price_per_1k_output,
                request_price=model.price_per_request, price_currency=model.price_currency,
                exchange_rate=row.exchange_rate), {'prompt_tokens': row.prompt_tokens or 0,
                                                 'completion_tokens': row.completion_tokens or 0})
            row.conversion_kind = 'legacy_estimated_historical_conversion'
    today_rate = rates.get(datetime.utcnow().date())
    for row in budgets:
        row.migration_exchange_rate = Decimal(today_rate['rate'])
        row.amount_cny = money(row.amount_usd, row.migration_exchange_rate)
    if needs_alert_conversion:
        rules['project_growth_min_cost_cny'] = float(money(rules['project_growth_min_cost_usd'], today_rate['rate']))
        config.config_value = json.dumps(rules)
    db.commit()
    return {'reservations': len(reservations), 'usages': len(usages), 'budgets': len(budgets)}


if __name__ == '__main__':
    with SessionLocal() as db:
        try:
            print(migrate(db))
            value = refresh_rate(db)
            if value is None:
                raise RuntimeError('账本已迁移，但无法获取最新汇率，暂不恢复美元模型准入')
            print({'rate': value['rate'], 'date': value['date'], 'source': value['source']})
        except BaseException:
            db.rollback()
            raise
