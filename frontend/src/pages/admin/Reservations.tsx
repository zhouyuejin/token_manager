import { useState } from 'react'
import dayjs from 'dayjs'
import { Alert, Button, Card, DatePicker, Descriptions, Select, Space, Table, Tag } from 'antd'
import { Reservation } from '../../api/billing'
import { Project } from '../../api/projects'
import { ExchangeRateStatus } from '../../components/ExchangeRateStatus'
import { modelDisplayName } from '../../utils/modelDisplayName.mjs'
import { userDisplayName } from '../../utils/userDisplayName.mjs'
import { useSwrData, useSwrDataWithParams } from '../../hooks/useSwr'

const Reservations = () => {
  const [month, setMonth] = useState(() => new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit'
  }).format(new Date()))
  const [reservationStatus, setReservationStatus] = useState<string>()
  const [reservationPage, setReservationPage] = useState(1)
  const { data: reservationData, error: reservationError, isLoading: reservationsLoading, mutate: mutateReservations } =
    useSwrDataWithParams<{ total: number; items: Reservation[] }>('/admin/billing/reservations', { month, page: reservationPage, page_size: 10, ...(reservationStatus ? { status: reservationStatus } : {}) })
  const { data: projects } = useSwrData<{ items: Project[] }>('/projects/admin')
  const money = (value: string | number) => {
    const n = Number(value)
    return `¥${n === 0 ? '0.00' : Math.abs(n) < 0.01 ? n.toFixed(8) : n.toFixed(2)}`
  }
  const reservationColumns = [
    { title: '状态', dataIndex: 'status', width: 90, render: (value: Reservation['status']) => <Tag color={value === 'reserved' ? 'blue' : value === 'committed' ? 'green' : 'default'}>{{ reserved: '预扣中', committed: '已结算', released: '已释放', expired: '已过期' }[value]}</Tag> },
    { title: '用户', dataIndex: 'user_id', width: 150, render: (_: string, row: Reservation) => userDisplayName(row) },
    { title: '项目', dataIndex: 'project_id', width: 150, render: (value: string | null) => value ? projects?.items.find(project => project.project_id === value)?.name || value : '无项目' },
    { title: '模型', dataIndex: 'model', width: 150, render: (value: string) => modelDisplayName(value) },
    { title: '预扣金额', dataIndex: 'estimated_cost_cny', width: 120, render: money },
    { title: '实际金额', dataIndex: 'actual_cost_cny', width: 120, render: (value: number | null) => value == null ? '—' : money(value) },
    { title: '创建时间', dataIndex: 'created_at', width: 180, render: (value: string) => dayjs.utc(value).utcOffset(8).format('YYYY-MM-DD HH:mm:ss') }
  ]
  return <div style={{ padding: 24 }}>
    <Card title="预扣与结算" extra={<Space wrap>
      <DatePicker picker="month" allowClear={false} value={dayjs(`${month}-01`)} onChange={value => {
        if (value) { setMonth(value.format('YYYY-MM')); setReservationPage(1) }
      }} />
      <Button onClick={() => mutateReservations()}>刷新</Button>
      <Select allowClear placeholder="全部状态" style={{ width: 140 }} value={reservationStatus} onChange={value => { setReservationStatus(value); setReservationPage(1) }} options={[
      { value: 'reserved', label: '预扣中' }, { value: 'committed', label: '已结算' },
      { value: 'released', label: '已释放' }, { value: 'expired', label: '已过期' }
    ]} /></Space>}>
      <ExchangeRateStatus />
      {reservationError && <Alert type="error" message="预扣记录加载失败" action={<Button onClick={() => mutateReservations()}>重试</Button>} />}
      <Table rowKey="reservation_id" loading={reservationsLoading} dataSource={reservationData?.items || []} columns={reservationColumns} scroll={{ x: 1050 }} expandable={{ expandedRowRender: row => <Descriptions size="small" column={2} items={[
        { key: 'key', label: 'API Key', children: row.key_id || '网页对话' },
        { key: 'estimated', label: '预估 Token', children: row.estimated_tokens.toLocaleString() },
        { key: 'actual', label: '实际 Token', children: row.actual_tokens?.toLocaleString() ?? '—' },
        { key: 'rate', label: '调用汇率快照', children: row.price_currency === 'USD' ? `${row.exchange_rate || '—'} (${row.exchange_rate_date?.slice(0, 10) || '—'})` : '人民币原价' },
      ]} /> }} pagination={{ current: reservationPage, pageSize: 10, total: reservationData?.total || 0, showSizeChanger: false, onChange: setReservationPage }} />
    </Card>
  </div>
}

export default Reservations
