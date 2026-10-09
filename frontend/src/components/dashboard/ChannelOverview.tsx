import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert, Button, Col, Empty, Row, Select, Space, Tooltip, Typography } from 'antd'
import { CloseCircleOutlined, WarningOutlined } from '@ant-design/icons'
import ReactECharts from '../AsyncECharts'
import { useThemeToken } from '../../theme/useThemeToken'
import { useSwrData } from '../../hooks/useSwr'
import { AdminProviderUsage } from '../../api/admin'
import { ChannelHealth } from '../../api/channels'
import { AlertRuleConfig } from '../../api/alerts'
import { channelState, channelStates, quotaSummary, topChannelUsage } from '../../utils/channelOverview.mjs'
import { formatTokenCount } from '../../utils/formatTokenCount.mjs'

type Props = { usage: AdminProviderUsage[]; range: string; loading: boolean; usageError?: boolean }

const ChannelOverview = ({ usage, range, loading, usageError }: Props) => {
  const { token } = useThemeToken()
  const navigate = useNavigate()
  const [metric, setMetric] = useState('tokens')
  const [updatedAt, setUpdatedAt] = useState('')
  const { data, error, isLoading, mutate } = useSwrData<{ items: ChannelHealth[] }>('/admin/health/channels', {
    refreshInterval: 30000,
    onSuccess: () => setUpdatedAt(new Date().toLocaleTimeString()),
  })
  const { data: quotas, error: quotaError } = useSwrData<{ items: any[] }>('/admin/channels/quotas', { refreshInterval: 30000 })
  const { data: rules } = useSwrData<AlertRuleConfig>('/admin/alerts/rules')
  useEffect(() => { if (data) setUpdatedAt(new Date().toLocaleTimeString()) }, [data])
  const quotaMap = Object.fromEntries((quotas?.items || []).map(row => [row.channel_id, quotaSummary(row, rules?.quota_remaining_percent)]))
  const channels = (data?.items || []).filter(row => row.status === 'active')
  const healthMap = Object.fromEntries((data?.items || []).map(row => [row.channel_id, row]))
  const stateOf = (row: ChannelHealth) => channelState(row, quotaMap[row.channel_id])
  const errorCount = channels.filter(row => stateOf(row).key === 'error').length
  const warningCount = channels.filter(row => stateOf(row).key === 'warning').length
  const top = topChannelUsage(usage, metric)
  const formatValue = (value: number) => metric === 'cost' ? `$${Number(value).toFixed(4)}` : metric === 'tokens' ? formatTokenCount(value) : Number(value).toLocaleString()
  const openChannel = (id: string) => navigate(`/admin/health?channel_id=${encodeURIComponent(id)}`)
  const statusOption = {
    title: { text: String(channels.length), subtext: '已启用渠道', left: 'center', top: '33%', textStyle: { color: token.colorText, fontSize: 28 }, subtextStyle: { color: token.colorTextSecondary } },
    tooltip: { trigger: 'item', renderMode: 'richText', formatter: '{b}：{c} 个' },
    legend: { bottom: 0, textStyle: { color: token.colorTextSecondary }, itemWidth: 10, itemHeight: 10 },
    series: [{ type: 'pie', radius: ['52%', '72%'], center: ['50%', '43%'], label: { show: false },
      data: Object.values(channelStates).filter(state => state.key !== 'disabled').map(state => ({
        name: state.label, state: state.key, value: channels.filter(row => stateOf(row).key === state.key).length,
        itemStyle: { color: state.color },
      })),
    }],
  }
  const usageOption = {
    tooltip: {
      trigger: 'axis', renderMode: 'richText', confine: true,
      formatter: (params: any) => {
        const row = top[params[0].dataIndex]
        const health = healthMap[row.channel_id]
        const quota = quotaMap[row.channel_id]
        const window = health?.windows['1h']
        return [row.channel, `用量：${formatValue(row[metric])}`, `当前状态：${channelState(health, quota).label}`,
          `近 1 小时成功率：${window?.requests ? `${window.success_rate}%` : '暂无调用'}`,
          `余额／配额：${quota?.text || '未接入余额／配额查询'}`,
          `配额更新：${quota?.updatedAt || '—'}`, `健康更新：${updatedAt || '—'}`,
          ...(health && channelState(health, quota).key === 'error' && health.recent_error ? [`异常原因：${health.recent_error}`] : [])].join('\n')
      },
    },
    grid: { left: 8, right: 50, top: 15, bottom: 25, containLabel: true },
    xAxis: { type: 'value', axisLabel: { color: token.colorTextSecondary, formatter: formatValue }, splitLine: { lineStyle: { color: token.colorBorderSecondary } } },
    yAxis: { type: 'category', inverse: true, data: top.map(row => row.channel), axisLabel: { color: token.colorText, width: 85, overflow: 'truncate' }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{ type: 'bar', barMaxWidth: 22, data: top.map(row => ({ value: row[metric], itemStyle: { color: channelState(healthMap[row.channel_id], quotaMap[row.channel_id]).color, borderRadius: [0, 4, 4, 0] } })) }],
  }

  return <>
    <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 8 }}>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>当前状态 · {updatedAt ? `${updatedAt} 更新` : '每 30 秒刷新'}</Typography.Text>
      <Space size={4}>
        {!error && errorCount > 0 && <Tooltip title={`${errorCount} 个渠道异常，点击查看`}>
          <Button type="text" size="small" aria-label={`${errorCount} 个渠道异常`} style={{ color: channelStates.error.color }} icon={<CloseCircleOutlined />} onClick={() => navigate('/admin/health?state=error')}>{errorCount}</Button>
        </Tooltip>}
        {!error && warningCount > 0 && <Tooltip title={`${warningCount} 个渠道预警，点击查看`}>
          <Button type="text" size="small" aria-label={`${warningCount} 个渠道预警`} style={{ color: channelStates.warning.color }} icon={<WarningOutlined />} onClick={() => navigate('/admin/health?state=warning')}>{warningCount}</Button>
        </Tooltip>}
        <Button type="link" size="small" onClick={() => navigate('/admin/health')}>查看全部</Button>
      </Space>
    </Space>
    {error && <Alert type="error" showIcon message="渠道健康加载失败" action={<Button size="small" onClick={() => mutate()}>重试</Button>} />}
    {quotaError && <Typography.Text type="warning">配额加载失败，预警信息可能不完整</Typography.Text>}
    <Row gutter={12}>
      <Col xs={24} sm={10}>
        {channels.length ? <ReactECharts option={statusOption} style={{ height: 230 }} opts={{ renderer: 'canvas' }}
          onEvents={{ click: (event: any) => navigate(`/admin/health?state=${event.data.state}`) }} />
          : <div style={{ height: 230, display: 'grid', placeItems: 'center' }}><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={isLoading ? '正在加载渠道' : error ? '健康数据不可用' : '暂无已启用渠道'} /></div>}
      </Col>
      <Col xs={24} sm={14}>
        <Space style={{ width: '100%', justifyContent: 'space-between', marginTop: 8 }}>
          <Typography.Text type="secondary">用量前 5</Typography.Text>
          <Select size="small" value={metric} onChange={setMetric} options={[{ value: 'tokens', label: 'Tokens' }, { value: 'requests', label: '请求数' }, { value: 'cost', label: '平台计费' }]} />
        </Space>
        {top.length && !usageError ? <ReactECharts option={usageOption} style={{ height: 190 }} opts={{ renderer: 'canvas' }}
          onEvents={{ click: (event: any) => openChannel(top[event.dataIndex].channel_id) }} />
          : <div style={{ height: 190, display: 'grid', placeItems: 'center' }}><Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={usageError ? '用量加载失败' : loading ? '正在加载用量' : '当前筛选暂无用量'} /></div>}
        <Typography.Text type="secondary" style={{ fontSize: 11 }}>{range} · 跟随页面筛选{metric === 'cost' ? '；历史未保存费用的渠道不参与排名' : ''}</Typography.Text>
      </Col>
    </Row>
  </>
}
export default ChannelOverview
