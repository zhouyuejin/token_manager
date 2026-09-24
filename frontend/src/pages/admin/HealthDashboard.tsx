import { useMemo, useState } from 'react'
import { Button, Card, Col, Empty, Progress, Row, Select, Space, Statistic, Table, Tag, Tooltip } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { useSwrData } from '../../hooks/useSwr'
import { useThemeToken } from '../../theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { getChannelHealth, recoverChannelHealth, ChannelHealth, ChannelHealthWindow } from '../../api/channels'

const windowOptions = [
  { value: '5m', label: '最近 5 分钟' },
  { value: '1h', label: '最近 1 小时' },
  { value: '24h', label: '最近 24 小时' },
] as const

const formatDate = (value?: string | null) => value ? new Date(value).toLocaleString() : '—'

const metricColor = (value: number) => value >= 99 ? '#16a34a' : value >= 95 ? '#d97706' : '#dc2626'

const WindowMetrics = ({ window }: { window: ChannelHealthWindow }) => (
  <Space direction="vertical" size={0} style={{ width: '100%' }}>
    <Progress percent={window.success_rate} size="small" strokeColor={metricColor(window.success_rate)} format={(value) => `${value}% 成功`} />
    <span style={{ color: '#64748b', fontSize: 12 }}>
      {window.requests} 请求 · P50 {window.p50_latency_ms ?? '—'}ms · P95 {window.p95_latency_ms ?? '—'}ms
    </span>
  </Space>
)

const HealthDashboard = () => {
  const [windowName, setWindowName] = useState<'5m' | '1h' | '24h'>('5m')
  const { data, isLoading, mutate } = useSwrData<{ items: ChannelHealth[] }>('/admin/health/channels')
  const { token } = useThemeToken()
  const message = useMessage()
  const items = data?.items || []
  const selectedWindow = useMemo(() => items.reduce((acc, item) => {
    const current = item.windows[windowName]
    acc.requests += current.requests
    acc.successes += current.successes
    acc.errors += current.errors
    return acc
  }, { requests: 0, successes: 0, errors: 0 }), [items, windowName])

  const recover = async (channel: ChannelHealth) => {
    try {
      await recoverChannelHealth(channel.channel_id)
      message.success(`${channel.name} cooldown 已恢复`)
      mutate()
    } catch {
      message.error('恢复 cooldown 失败')
    }
  }

  const columns = [
    { title: '渠道', dataIndex: 'name', key: 'name', render: (name: string, row: ChannelHealth) => <Space direction="vertical" size={0}><span>{name}</span><span style={{ color: '#64748b', fontSize: 12 }}>{row.channel_id}</span></Space> },
    { title: '健康状态', dataIndex: 'health_status', key: 'health_status', render: (value: string) => <Tag color={value === 'healthy' ? 'green' : value === 'degraded' ? 'orange' : 'red'}>{value}</Tag> },
    { title: windowOptions.find(item => item.value === windowName)?.label, key: 'metrics', width: 300, render: (_: unknown, row: ChannelHealth) => <WindowMetrics window={row.windows[windowName]} /> },
    { title: 'Cooldown', key: 'cooldown', render: (_: unknown, row: ChannelHealth) => <Space direction="vertical" size={0}>{row.cooldown.channel_until ? <Tag color="orange">渠道至 {formatDate(row.cooldown.channel_until)}</Tag> : <Tag color="green">渠道正常</Tag>}{row.cooldown.keys.length > 0 && <span style={{ color: '#d97706', fontSize: 12 }}>{row.cooldown.keys.length} 个 Key 冷却中</span>}</Space> },
    { title: '最近错误', dataIndex: 'recent_error', key: 'recent_error', ellipsis: true, render: (value: string | null) => value ? <Tooltip title={value}>{value}</Tooltip> : '—' },
    { title: '操作', key: 'action', render: (_: unknown, row: ChannelHealth) => <Button size="small" disabled={!row.cooldown.channel_until && row.cooldown.keys.length === 0} onClick={() => recover(row)}>恢复 cooldown</Button> },
  ]

  return <div style={{ padding: 24, background: token.colorBgLayout, minHeight: '100%' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
      <div><h2 style={{ marginBottom: 4 }}>渠道健康看板</h2><span style={{ color: '#64748b' }}>基于代理用量日志实时聚合</span></div>
      <Space><Select value={windowName} options={[...windowOptions]} onChange={setWindowName} /><Button icon={<ReloadOutlined />} onClick={() => mutate()}>刷新</Button></Space>
    </div>
    <Row gutter={16} style={{ marginBottom: 16 }}>
      <Col xs={24} sm={8}><Card><Statistic title="请求数" value={selectedWindow.requests} /></Card></Col>
      <Col xs={24} sm={8}><Card><Statistic title="成功数" value={selectedWindow.successes} valueStyle={{ color: '#16a34a' }} /></Card></Col>
      <Col xs={24} sm={8}><Card><Statistic title="错误数" value={selectedWindow.errors} valueStyle={{ color: selectedWindow.errors ? '#dc2626' : '#16a34a' }} /></Card></Col>
    </Row>
    <Card title="渠道指标" bodyStyle={{ padding: 0 }}>
      {items.length ? <Table rowKey="channel_id" columns={columns} dataSource={items} loading={isLoading} pagination={false} scroll={{ x: 1100 }} /> : <Empty description="暂无渠道健康数据" />}
    </Card>
  </div>
}

export default HealthDashboard
