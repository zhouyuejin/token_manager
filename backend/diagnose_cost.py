"""诊断脚本：为什么 admin 仪表盘的「预估费用」是 0

跑法（先确保在 backend 目录）：
    python diagnose_cost.py

输出会按下面 4 步告诉你卡在哪一步：
  1. ModelMapping 表里哪些模型设了价格
  2. UsageLog 表里实际出现过哪些 model 字符串
  3. UsageLog.model 能不能匹配到 ModelMapping.model_id 或 provider_model
  4. 匹配上的那些 model 里，prompt/completion token 是不是 0（如果是，价格再大也乘不出钱）
"""
import sys
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# 复用项目里的配置
from app.core.config import settings
from app.core.database import Base
from app.models.model_mapping import ModelMapping
from app.models.usage_log import UsageLog


def main():
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        print('=' * 70)
        print('STEP 1 — ModelMapping 表里设了非零价格的模型')
        print('=' * 70)
        priced = db.query(ModelMapping).filter(
            (ModelMapping.price_per_1k_input > 0) |
            (ModelMapping.price_per_1k_output > 0) |
            (ModelMapping.price_per_request > 0)
        ).all()
        if not priced:
            print('  ⚠️  没有模型设过价格 —— 这是 cost=0 的最常见原因。')
            print('     去「模型管理」里给模型配上 price_per_1k_input/output。')
            return
        for m in priced:
            print(f'  model_id={m.model_id!r:30s} provider_model={m.provider_model!r:30s} '
                  f'in={m.price_per_1k_input} out={m.price_per_1k_output} req={m.price_per_request}')

        print()
        print('=' * 70)
        print('STEP 2 — UsageLog 表里实际出现过的 model 字符串（最近 7 天）')
        print('=' * 70)
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        rows = db.query(
            UsageLog.model,
            func.count(UsageLog.id).label('n'),
            func.coalesce(func.sum(UsageLog.prompt_tokens), 0).label('prompt'),
            func.coalesce(func.sum(UsageLog.completion_tokens), 0).label('completion'),
        ).filter(func.date(UsageLog.created_at) >= cutoff
        ).group_by(UsageLog.model).all()
        if not rows:
            print('  ⚠️  最近 7 天 UsageLog 是空的 —— 没有数据可算费用。')
            print('     试试把仪表盘的时间范围调大，或先发几条请求。')
            return
        used_models = set()
        for r in rows:
            print(f'  UsageLog.model={r.model!r:30s} 行数={int(r.n):>5d} '
                  f'prompt={int(r.prompt):>8d} completion={int(r.completion):>8d}')
            used_models.add(r.model)

        print()
        print('=' * 70)
        print('STEP 3 — 上面这些 UsageLog.model 能不能对上 ModelMapping')
        print('=' * 70)
        mappings_by_id = {m.model_id: m for m in db.query(ModelMapping).all()}
        mappings_by_pm = {m.provider_model: m for m in db.query(ModelMapping).all() if m.provider_model}
        matched, unmatched = [], []
        for name in sorted(used_models):
            hit = mappings_by_id.get(name) or mappings_by_pm.get(name)
            if hit:
                matched.append((name, hit))
            else:
                unmatched.append(name)
        if matched:
            print('  ✓ 已匹配：')
            for name, m in matched:
                via = 'model_id' if name == m.model_id else 'provider_model'
                print(f'    UsageLog.model={name!r} ← {via} of {m.model_id}')
        if unmatched:
            print('  ✗ 未匹配（这些 UsageLog 行的 cost 永远会是 0）：')
            for name in unmatched:
                print(f'    UsageLog.model={name!r}')
                # 试着给出建议
                if name in (m.provider_model for m in db.query(ModelMapping).all()):
                    print('        ⚠️  这个名字等于某个 ModelMapping.provider_model，理论上能匹配。')
                elif name in (m.model_id for m in db.query(ModelMapping).all()):
                    print('        ⚠️  这个名字等于某个 ModelMapping.model_id，理论上能匹配。')

        print()
        print('=' * 70)
        print('STEP 4 — 匹配上的那些模型，token 累加值')
        print('=' * 70)
        for name, m in matched:
            totals = db.query(
                func.coalesce(func.sum(UsageLog.prompt_tokens), 0),
                func.coalesce(func.sum(UsageLog.completion_tokens), 0),
            ).filter(UsageLog.model == name
            ).filter(func.date(UsageLog.created_at) >= cutoff).first()
            in_price = float(m.price_per_1k_input or 0)
            out_price = float(m.price_per_1k_output or 0)
            cost = float(totals[0]) / 1000 * in_price + float(totals[1]) / 1000 * out_price
            print(f'  {name!r:30s} prompt={int(totals[0]):>8d} completion={int(totals[1]):>8d} '
                  f'cost=${cost:.6f}')

        if all(r.prompt == 0 and r.completion == 0 for r in rows):
            print('  ⚠️  所有 UsageLog 行的 prompt_tokens 和 completion_tokens 都是 0。')
            print('     这会让 cost 永远是 0，无论价格怎么配。')
            print('     排查方向：record_usage 调用时上游是否回传了真实 token 数。')
    finally:
        db.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'\n诊断脚本出错：{e}', file=sys.stderr)
        sys.exit(1)
