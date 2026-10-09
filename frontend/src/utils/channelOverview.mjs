export const channelStates = {
  healthy: { key: 'healthy', label: '正常', color: '#10B981' },
  error: { key: 'error', label: '异常', color: '#EF4444' },
  warning: { key: 'warning', label: '配额偏低／降级', color: '#F59E0B' },
  unknown: { key: 'unknown', label: '待验证', color: '#94A3B8' },
  disabled: { key: 'disabled', label: '已禁用', color: '#64748B' },
}

export function channelState(health, quota = {}) {
  if (health?.status === 'disabled') return channelStates.disabled
  if (health?.health_status === 'unhealthy' || quota.unavailable) return channelStates.error
  const cooling = health?.cooldown?.channel_until && new Date(health.cooldown.channel_until) > new Date()
  if (health?.health_status === 'degraded' || cooling || quota.low) return channelStates.warning
  if (!health || (!health.last_check_at && !health.windows?.['24h']?.requests)) return channelStates.unknown
  return channelStates.healthy
}

export function quotaSummary(quota, threshold = 20) {
  const windows = quota?.windows || []
  const balance = windows.map(w => w.raw_data?.window?.raw_data).find(data => data?.balance_infos || data?.balance)
  const balances = balance?.balance_infos || (balance?.balance ? [balance.balance] : [])
  const unavailable = balance?.is_available === false || balances.some(b => b.total_balance != null && Number(b.total_balance) <= 0)
  const limited = windows.filter(w => Number(w.limit) > 0 && w.remain != null)
  const low = unavailable || limited.some(w => Number(w.remain) / Number(w.limit) * 100 <= threshold)
  const text = balances.length
    ? balances.map(b => `${b.total_balance} ${b.currency || ''}`).join(' / ')
    : limited.map(w => `${w.label || w.type || '配额'}：剩余 ${w.remain} / ${w.limit}`).join('；') || '未接入余额／配额查询'
  return { text, low, unavailable, updatedAt: windows.map(w => w.last_sync).filter(Boolean).sort().at(-1) }
}

export function topChannelUsage(rows = [], metric = 'tokens') {
  return rows.filter(row => row.channel_id && Number(row[metric]) > 0)
    .slice().sort((a, b) => Number(b[metric]) - Number(a[metric])).slice(0, 5)
}
