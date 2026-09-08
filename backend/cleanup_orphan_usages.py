"""一次性清理：删除指向不存在 ModelMapping 的 UsageLog 行。

背景：
    当 admin 删除 ModelMapping 或 Provider 时，旧版代码只删了映射本身，
    UsageLog 里指向那个 model 的历史行成了"孤儿"，统计时 cost 永远 = 0。
    新版已经修了 delete_provider / delete_model_mapping，但**已经存在**的
    孤儿行还在。这个脚本用来一次性清掉它们。

跑法（默认 dry-run，只打印不删）：
    python cleanup_orphan_usages.py

确认要删（真的会删）：
    python cleanup_orphan_usages.py --delete

输出格式：
    - 按 model 维度统计孤儿行数和总 token
    - 合计行数
    - 加 --delete 后才执行 DELETE
"""
import argparse
import sys
from sqlalchemy import create_engine, func, delete

from app.core.config import settings
from app.core.database import Base
from app.models.model_mapping import ModelMapping
from app.models.usage_log import UsageLog

import app.models  # noqa: F401, E402


def main():
    parser = argparse.ArgumentParser(description="清理孤儿 UsageLog 行（指向不存在 ModelMapping 的）")
    parser.add_argument("--delete", action="store_true",
                        help="真的执行 DELETE；不加则只打印预览")
    args = parser.parse_args()

    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

    print('=' * 70)
    print('扫描孤儿 UsageLog 行（UsageLog.model 不在 ModelMapping.model_id 里）')
    print('=' * 70)

    # 一次 SQL 拿全所有孤儿行，统计每个 model 的行数 + token
    mapping_ids_subq = (
        engine.connect()
        .execution_options(stream_results=True)
    )

    # 用子查询列出所有 ModelMapping.model_id
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    try:
        all_model_ids = {m.model_id for m in db.query(ModelMapping.model_id).all()}
        print(f'ModelMapping 总数：{len(all_model_ids)}')

        # 找出所有孤儿行
        orphan_rows = db.query(
            UsageLog.model,
            func.count(UsageLog.id).label('rows'),
            func.coalesce(func.sum(UsageLog.prompt_tokens), 0).label('prompt'),
            func.coalesce(func.sum(UsageLog.completion_tokens), 0).label('completion'),
        ).group_by(UsageLog.model).all()

        orphans = [r for r in orphan_rows if r.model not in all_model_ids]

        if not orphans:
            print('✅ 没有孤儿行，数据库是干净的。')
            return

        total_rows = 0
        total_prompt = 0
        total_completion = 0
        print()
        print(f'{"model":<35} {"行数":>8} {"prompt":>10} {"completion":>12}')
        print('-' * 70)
        for r in sorted(orphans, key=lambda x: -x.rows):
            print(f'{r.model:<35} {int(r.rows):>8d} {int(r.prompt):>10d} {int(r.completion):>12d}')
            total_rows += int(r.rows)
            total_prompt += int(r.prompt)
            total_completion += int(r.completion)

        print('-' * 70)
        print(f'{"合计":<35} {total_rows:>8d} {total_prompt:>10d} {total_completion:>12d}')

        if not args.delete:
            print()
            print('⚠️  以上只是预览，未删除任何行。')
            print('    确认无误后加 --delete 真正执行：')
            print('    python cleanup_orphan_usages.py --delete')
            return

        # 真的删
        print()
        print(f'⚡ 正在 DELETE {total_rows} 条孤儿行...')
        # 重新查询确认 (避免刚才 print 之后又被人改了)
        # 直接按 model 列表 DELETE
        orphan_model_names = [r.model for r in orphans]
        deleted = db.query(UsageLog).filter(
            UsageLog.model.in_(orphan_model_names)
        ).delete(synchronize_session=False)
        db.commit()
        print(f'✅ 已删除 {deleted} 条 UsageLog 行。')
        print()
        print('建议跑一次诊断脚本确认数据库已经干净：')
        print('    python diagnose_cost.py')
    finally:
        db.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'\n清理脚本出错：{e}', file=sys.stderr)
        sys.exit(1)
