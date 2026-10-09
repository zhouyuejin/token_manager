import { Alert } from 'antd'
import { useSwrData } from '../hooks/useSwr'

type Rate = { available: boolean; stale: boolean; rate?: string; date?: string; fetched_at?: string; source: string }

export const ExchangeRateStatus = () => {
  const { data, error } = useSwrData<Rate>('/admin/billing/exchange-rate', { refreshInterval: 60000 })
  if (!data && !error) return null
  return <Alert showIcon style={{ marginBottom: 16 }}
    type={error || !data?.available ? 'error' : data.stale ? 'warning' : 'info'}
    message={error ? '汇率状态加载失败' : !data?.available ? '尚无有效 USD/CNY 汇率，美元来源模型暂不能计费' :
      `1 USD = ¥${data.rate} · 汇率日期 ${data.date} · ${data.source} · 获取于 ${data.fetched_at ? new Date(data.fetched_at).toLocaleString() : '—'}${data.stale ? ' · 使用最近成功汇率' : ''}`}
    description="自动获取最新公布的日频参考汇率，每小时刷新。调用时冻结汇率与费用，预扣和结算使用同一快照，历史账单不会随汇率变化。手工录入价格及预算均为人民币。" />
}
