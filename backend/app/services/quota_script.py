"""Run quota JavaScript in a disposable process, with no JS system bindings."""
import asyncio
import json
import sys
from decimal import Decimal, InvalidOperation


async def execute_quota_script(script, endpoint, api_key, timeout=15):
    if not isinstance(script, str) or not script.strip() or len(script) > 32768:
        raise ValueError('查询脚本不能为空且不能超过 32768 字符')
    process = await asyncio.create_subprocess_exec(
        sys.executable, '-m', 'app.services.quota_script_worker',
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(json.dumps({
            'script': script, 'endpoint': endpoint, 'api_key': api_key,
        }).encode()), timeout=timeout)
    except (asyncio.TimeoutError, asyncio.CancelledError) as error:
        if process.returncode is None:
            process.kill()
        await process.communicate()
        if isinstance(error, asyncio.CancelledError):
            raise
        raise ValueError('查询脚本执行超时') from error
    if process.returncode or len(output) > 1_048_576:
        raise ValueError('查询脚本执行失败或超过资源限制')
    result = json.loads(output)
    if result.get('error'):
        raise ValueError(result['error'])
    data = result.get('data')
    if not isinstance(data, dict):
        raise ValueError('脚本必须返回包含 balance 或 windows 的对象')
    if 'balance' in data:
        balance = data['balance']
        try:
            amount = Decimal(str(balance['total_balance']))
            if not amount.is_finite() or not isinstance(balance['currency'], str) or not balance['currency']:
                raise ValueError()
        except (KeyError, TypeError, ValueError, InvalidOperation):
            raise ValueError('balance 必须包含 currency 和有效的 total_balance')
        data['windows'] = [{'type': 'custom', 'label': '账户余额', 'raw_data': {'balance': balance}}]
    windows = data.get('windows')
    if not isinstance(windows, list) or not windows:
        raise ValueError('脚本必须返回 balance 或非空 windows')
    types = set()
    for window in windows:
        if not isinstance(window, dict) or window.get('type') not in {'hourly', 'five_hour', 'weekly', 'daily', 'monthly', 'custom'}:
            raise ValueError('windows 中包含无效的配额类型')
        if window['type'] in types:
            raise ValueError('windows 的配额类型不能重复')
        types.add(window['type'])
        if window.get('label') is not None and not isinstance(window['label'], str):
            raise ValueError('配额 label 必须是字符串')
        if window.get('reset_at') is not None and not isinstance(window['reset_at'], str):
            raise ValueError('reset_at 必须是时间字符串')
        for field in ('limit', 'used', 'remain', 'percent', 'reset_in_seconds'):
            if window.get(field) is None:
                continue
            try:
                value = Decimal(str(window[field]))
                maximum = 100 if field == 'percent' else 2**63 - 1
                if not value.is_finite() or not 0 <= value <= maximum or (field != 'percent' and value != int(value)):
                    raise ValueError()
            except (ValueError, InvalidOperation):
                raise ValueError(f'配额 {field} 无效')
    return {**data, 'provider': 'script'}
