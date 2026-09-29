import { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Col, Empty, Form, InputNumber, Popconfirm, Progress, Row, Select, Space, Statistic, Table, Tag, Tooltip } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import useSWR from 'swr'
import { useSwrData } from '../../hooks/useSwr'
import { useThemeToken } from '../../theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { WriteOnly } from '../../components/WriteOnly'
import { getChannelHealth, recoverChannelHealth, ChannelHealth, ChannelHealthWindow } from '../../api/channels'
import { getAlertRules, updateAlertRules, AlertRuleConfig } from '../../api/alerts'
import { useAuthStore } from '../../store/auth'
import { hasPermission } from '../../utils/adminPermissions.mjs'

const windowOptions = [
  { value: '5m', label: '最近 5 分钟' },
  { value: '1h', label: '最近 1 小时' },
  { value: '24h', label: '最近 24 小时' },
] as const

const formatDate = (value?: string | null) => value ? new Date(value).toLocaleString() : '—'

const metricColor = (value: number) => value >= 99 ? '#16a34a' : value >= 95 ? '#d97706' : '#dc2626'
const healthLabels: Record<string, string> = { healthy: '健康', degraded: '降级', unhealthy: '不健康' }
const componentLabels: Record<string, string> = { mysql: 'MySQL', redis: 'Redis', upstream: '上游', background_tasks: '后台任务', not_configured: '未配置', unknown: '未知' }

const fetchSystemHealth = async () => {
  const response = await fetch('/health')
  const data = await response.json()
  if (!response.ok && response.status !== 503) throw new Error('健康状态请求失败')
  return data as { status: string; components: Record<string, string> }
}

const WindowMetrics = ({ window }: { window: ChannelHealthWindow }) => (
  <Space direction="vertical" size={0} style={{ width: '100%' }}>
    <Progress percent={window.success_rate} size="small" strokeColor={metricColor(window.success_rate)} format={(value) => `${value}% 成功`} />
    <span style={{ color: '#64748b', fontSize: 12 }}>
      {window.requests} 请求 · 错误率 {window.error_rate}% · P50 {window.p50_latency_ms ?? '—'}ms · P95 {window.p95_latency_ms ?? '—'}ms
    </span>
  </Space>
)

const HealthDashboard = () => {
  const [windowName, setWindowName] = useState<'5m' | '1h' | '24h'>('5m')
  const [form] = Form.useForm<AlertRuleConfig>()
  const [savingRules, setSavingRules] = useState(false)
  const { data, isLoading, mutate } = useSwrData<{ items: ChannelHealth[] }>('/admin/health/channels')
  const { data: systemHealth, error: systemHealthError, mutate: refreshSystemHealth } = useSWR('/health', fetchSystemHealth, { refreshInterval: 30000, shouldRetryOnError: false })
  const { data: alertRules, error: alertRulesError, isLoading: alertRulesLoading, mutate: mutateAlertRules } = useSWR('/admin/alerts/rules', getAlertRules)
  const { token } = useThemeToken()
  const message = useMessage()
  const permissions = useAuthStore((state) => state.user?.permissions || [])
  const canEditRules = hasPermission(permissions, 'admin:write')
  const items = data?.items || []
  useEffect(() => {
    if (alertRules) form.setFieldsValue(alertRules)
  }, [alertRules, form])
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

  const saveAlertRules = async (values: AlertRuleConfig) => {
    setSavingRules(true)
    try {
      const saved = await updateAlertRules(values)
      form.setFieldsValue(saved)
      await mutateAlertRules(saved, false)
      message.success('告警规则保存成功')
    } catch {
      message.error('告警规则保存失败')
    } finally {
      setSavingRules(false)
    }
  }

  const columns = [
    { title: '渠道', dataIndex: 'name', key: 'name', render: (name: string, row: ChannelHealth) => <Space direction="vertical" size={0}><span>{name}</span><span style={{ color: '#64748b', fontSize: 12 }}>{row.channel_id}</span></Space> },
    { title: '健康状态', dataIndex: 'health_status', key: 'health_status', render: (value: string) => <Tag color={value === 'healthy' ? 'green' : value === 'degraded' ? 'orange' : 'red'}>{healthLabels[value] || value || '未知'}</Tag> },
    { title: windowOptions.find(item => item.value === windowName)?.label, key: 'metrics', width: 300, render: (_: unknown, row: ChannelHealth) => <WindowMetrics window={row.windows[windowName]} /> },
    { title: 'Cooldown', key: 'cooldown', render: (_: unknown, row: ChannelHealth) => <Space direction="vertical" size={0}>{row.cooldown.channel_until ? <Tag color="orange">渠道至 {formatDate(row.cooldown.channel_until)}</Tag> : <Tag color="green">渠道正常</Tag>}{row.cooldown.keys.length > 0 && <span style={{ color: '#d97706', fontSize: 12 }}>{row.cooldown.keys.length} 个 Key 冷却中</span>}</Space> },
    { title: '最近错误', dataIndex: 'recent_error', key: 'recent_error', ellipsis: true, render: (value: string | null) => value ? <Tooltip title={value}>{value}</Tooltip> : '—' },
    { title: '操作', key: 'action', render: (_: unknown, row: ChannelHealth) => <WriteOnly><Popconfirm title="确认恢复该渠道及其 Key 的 cooldown？" onConfirm={() => recover(row)}><Button size="small" disabled={!row.cooldown.channel_until && row.cooldown.keys.length === 0}>恢复 cooldown</Button></Popconfirm></WriteOnly> },
  ]

  return <div style={{ padding: 24, background: token.colorBgLayout, minHeight: '100%' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
      <div><h2 style={{ marginBottom: 4 }}>渠道健康看板</h2><span style={{ color: '#64748b' }}>基于代理用量日志实时聚合</span></div>
      <Space><Select value={windowName} options={[...windowOptions]} onChange={setWindowName} /><Button icon={<ReloadOutlined />} onClick={() => { mutate(); refreshSystemHealth() }}>刷新</Button></Space>
    </div>
    {systemHealthError ? <Alert type="error" showIcon style={{ marginBottom: 16 }} message="系统健康状态加载失败" description="无法读取 /health，请检查服务可用性和网络连接。" /> : systemHealth && <Card title="系统依赖与任务状态" style={{ marginBottom: 16 }}>
      <Space wrap>
        <Tag color={systemHealth.status === 'healthy' ? 'green' : systemHealth.status === 'degraded' ? 'orange' : 'red'}>{healthLabels[systemHealth.status] || systemHealth.status}</Tag>
        {Object.entries(systemHealth.components).map(([name, status]) => <Tag key={name} color={status === 'healthy' ? 'green' : status === 'not_configured' ? 'default' : 'orange'}>{componentLabels[name] || name}：{healthLabels[status] || componentLabels[status] || status}</Tag>)}
      </Space>
      {systemHealth.status !== 'healthy' && <Alert type={systemHealth.status === 'unhealthy' ? 'error' : 'warning'} showIcon style={{ marginTop: 12 }} message="请先检查上方异常组件；上游探测和后台任务状态可在下方渠道明细中进一步排查。" />}
    </Card>}
    <Card title="告警规则" loading={alertRulesLoading} style={{ marginBottom: 16 }}>
      {alertRulesError ? <Alert type="error" showIcon message="告警规则加载失败" description="请刷新后重试。" /> : <Form form={form} layout="vertical" onFinish={saveAlertRules}>
        <Row gutter={16}>
          <Col xs={24} md={12}>
            <Form.Item name="channel_error_rate_percent" label="渠道错误率阈值" extra="百分比（0–100%）；最近 5 分钟达到该值时触发。" rules={[{ required: true }]}>
              <InputNumber min={0} max={100} step={1} disabled={!canEditRules} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="channel_error_min_requests" label="触发所需最小请求数" extra="整数（≥1）；统计最近 5 分钟的请求。" rules={[{ required: true }]}>
              <InputNumber min={1} step={1} precision={0} disabled={!canEditRules} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="quota_remaining_percent" label="上游配额余量阈值" extra="百分比（0–100%）；余量小于或等于该值时触发。" rules={[{ required: true }]}>
              <InputNumber min={0} max={100} step={1} disabled={!canEditRules} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="project_growth_multiplier" label="项目消费增长倍数" extra="倍数（>0）；比较最近 1 小时与此前 24 小时的平均每小时消费。" rules={[{ required: true }, { validator: (_, value) => value > 0 ? Promise.resolve() : Promise.reject(new Error('必须大于 0')) }]}>
              <InputNumber min={0} step={0.1} disabled={!canEditRules} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="project_growth_min_cost_usd" label="项目最小消费额" extra="美元（≥0）；最近 1 小时消费达到该值后才比较增长倍数。" rules={[{ required: true }]}>
              <InputNumber min={0} step={0.01} disabled={!canEditRules} style={{ width: '100%' }} />
            </Form.Item>
          </Col>
        </Row>
        <WriteOnly><Button type="primary" htmlType="submit" loading={savingRules} disabled={!alertRules}>保存告警规则</Button></WriteOnly>
      </Form>}
    </Card>
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
