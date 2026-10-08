import { useEffect, useState } from 'react'
import { Button, Card, Input, InputNumber, Space, Table, Tag, Typography } from 'antd'
import { CopyOutlined, ReloadOutlined, SearchOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useThemeToken } from '../../theme/useThemeToken'
import { useMessage } from '../../utils/message'
import { getRouteDecisionLogs, RouteDecisionLog, RouteDecisionLogParams } from '../../api/logs'
import { Channel } from '../../api/channels'
import { useSwrData } from '../../hooks/useSwr'

const RouteMonitor = () => {
  const { token } = useThemeToken()
  const message = useMessage()
  const { data: channels } = useSwrData<{ items: Channel[] }>('/admin/channels')
  const [items, setItems] = useState<RouteDecisionLog[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [filters, setFilters] = useState({ request_id: '', user_id: '', key_id: '', model: '', channel_id: '', status_code: undefined as number | undefined })

  const fetchData = async (nextPage = page, overrides?: Partial<typeof filters>, nextPageSize = pageSize) => {
    setLoading(true)
    try {
      const params: RouteDecisionLogParams = { page: nextPage, page_size: nextPageSize }
      Object.entries({ ...filters, ...overrides }).forEach(([key, value]) => {
        if (value !== '' && value !== undefined) Object.assign(params, { [key]: value })
      })
      const result = await getRouteDecisionLogs(params)
      setItems(result.items)
      setTotal(result.total)
      setPage(nextPage)
    } catch (error) {
      console.error(error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(1)
  }, [])

  const columns = [
    { title: '时间', dataIndex: 'created_at', key: 'created_at', render: (value: string) => dayjs.utc(value).local().format('YYYY-MM-DD HH:mm:ss') },
    { title: 'Request ID', dataIndex: 'request_id', key: 'request_id', render: (value: string) => <Space size={4}><Typography.Text code copyable={{ text: value }}>{value}</Typography.Text><Button size="small" type="text" icon={<CopyOutlined />} onClick={() => { void navigator.clipboard.writeText(value); message.success('已复制 Request ID') }} /></Space> },
    { title: '用户', dataIndex: 'username', key: 'username', render: (_: string | null | undefined, row: RouteDecisionLog) => row.username || row.user_id || '—' },
    { title: '模型', dataIndex: 'model', key: 'model', render: (value: string) => {
      const channelType = channels?.items.find(channel => value.startsWith(`${channel.type}-`))?.type
      return channelType ? value.slice(channelType.length + 1) : value
    } },
    { title: '状态', dataIndex: 'status_code', key: 'status_code', render: (value: number) => <Tag color={value === 200 ? 'green' : 'red'}>{value}</Tag> },
    { title: '最终渠道', dataIndex: 'selected_channel', key: 'selected_channel', render: (value: string | null) => value || '—' },
  ]

  const expandedRowRender = (row: RouteDecisionLog) => (
    <Space direction="vertical" style={{ width: '100%' }}>
      <div><b>候选渠道：</b>{row.candidate_channels.join(', ') || '—'}</div>
      <div><b>跳过原因：</b>{Object.entries(row.skipped_reasons).map(([channel, reason]) => `${channel}: ${reason}`).join('；') || '—'}</div>
      <div><b>失败重试路径：</b>{row.retry_path.map(item => `${item.channel_id} (${item.status_code})`).join(' → ') || '—'}</div>
      {row.error_message && <Typography.Text type="danger"><b>错误摘要：</b>{row.error_message}</Typography.Text>}
    </Space>
  )

  return <div style={{ padding: 24, background: token.colorBgLayout, minHeight: '100%' }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
      <div><h2 style={{ marginBottom: 4 }}>路由监控</h2><span style={{ color: '#64748b' }}>按请求定位路由决策并查看失败路径</span></div>
      <Button icon={<ReloadOutlined />} onClick={() => fetchData()}>刷新</Button>
    </div>
    <Card style={{ marginBottom: 16 }}>
      <Space wrap>
        <Input placeholder="Request ID" value={filters.request_id} onChange={event => setFilters({ ...filters, request_id: event.target.value })} onPressEnter={() => fetchData(1)} />
        <Input placeholder="用户 ID" value={filters.user_id} onChange={event => setFilters({ ...filters, user_id: event.target.value })} />
        <Input placeholder="Key ID" value={filters.key_id} onChange={event => setFilters({ ...filters, key_id: event.target.value })} />
        <Input placeholder="模型" value={filters.model} onChange={event => setFilters({ ...filters, model: event.target.value })} />
        <Input placeholder="渠道 ID" value={filters.channel_id} onChange={event => setFilters({ ...filters, channel_id: event.target.value })} />
        <InputNumber placeholder="状态码" value={filters.status_code} onChange={value => setFilters({ ...filters, status_code: value ?? undefined })} />
        <Button icon={<SearchOutlined />} type="primary" onClick={() => fetchData(1)}>查询</Button>
      </Space>
    </Card>
    <Card>
      <Table rowKey="id" columns={columns} dataSource={items} loading={loading} expandable={{ expandedRowRender }} pagination={{ current: page, pageSize, total, showSizeChanger: true, showTotal: count => `共 ${count} 条`, onChange: (nextPage, nextPageSize) => { setPageSize(nextPageSize); fetchData(nextPage, undefined, nextPageSize) } }} />
    </Card>
  </div>
}

export default RouteMonitor
