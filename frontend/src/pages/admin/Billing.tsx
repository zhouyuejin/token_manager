import { useState } from 'react'
import { Alert, Button, Card, DatePicker, Drawer, Form, InputNumber, Modal, Select, Space, Switch, Table, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import { useNavigate } from 'react-router-dom'
import { Budget, BudgetSave, ReconcileItem, ReconcileReport, ReconcileReportList, Reservation, runReconcile, saveBudget } from '../../api/billing'
import { Department, Project } from '../../api/projects'
import { useSwrData, useSwrDataWithParams } from '../../hooks/useSwr'
import { useMessage } from '../../utils/message'

const Billing = () => {
  const navigate = useNavigate()
  const [month, setMonth] = useState(() => new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit'
  }).format(new Date()))
  const { data, error, isLoading, mutate } = useSwrDataWithParams<{ items: Budget[] }>('/admin/billing/budgets', { month })
  const [reservationStatus, setReservationStatus] = useState<string>()
  const { data: reservationData, error: reservationError, isLoading: reservationsLoading, mutate: mutateReservations } =
    useSwrDataWithParams<{ items: Reservation[] }>('/admin/billing/reservations', { month, ...(reservationStatus ? { status: reservationStatus } : {}) })
  const { data: projects, error: projectsError } = useSwrData<{ items: Project[] }>('/projects/admin')
  const { data: departments, error: departmentsError } = useSwrData<{ items: Department[] }>('/projects/admin/departments')
  const [visible, setVisible] = useState(false)
  const [editing, setEditing] = useState<Budget | null>(null)
  const [saving, setSaving] = useState(false)
  const [reportPage, setReportPage] = useState(1)
  const [selectedReport, setSelectedReport] = useState<ReconcileReport | null>(null)
  const [itemPage, setItemPage] = useState(1)
  const [anomalyType, setAnomalyType] = useState<string>()
  const [rerunning, setRerunning] = useState<string>()
  const { data: reportData, error: reportError, isLoading: reportsLoading, mutate: mutateReports } =
    useSwrDataWithParams<ReconcileReportList>('/admin/billing/reconcile/reports', { page: reportPage, page_size: 20 })
  const { data: itemData, error: itemError, isLoading: itemsLoading } = useSwrDataWithParams<{ total: number; items: ReconcileItem[] }>(
    selectedReport ? `/admin/billing/reconcile/reports/${selectedReport.report_id}/items` : null,
    selectedReport ? { page: itemPage, page_size: 20, ...(anomalyType ? { anomaly_type: anomalyType } : {}) } : null,
  )
  const [form] = Form.useForm()
  const kind: Budget['scope_type'] = Form.useWatch('scope_type', form) || 'project'
  const message = useMessage()

  const rerun = async (report: ReconcileReport) => {
    setRerunning(report.report_id)
    try {
      await runReconcile(report.business_date)
      message.success(`${report.business_date} 对账已完成`)
      mutateReports()
    } catch { /* 请求拦截器显示错误 */ }
    finally { setRerunning(undefined) }
  }

  const open = (row: Budget | null) => {
    setEditing(row)
    form.resetFields()
    form.setFieldsValue(row ? { ...row, amount_usd: String(row.amount_usd) } : {
      scope_type: 'project', amount_usd: '0', thresholds: [80, 90, 100], policy: 'block', enabled: true
    })
    setVisible(true)
  }

  const save = async (values: BudgetSave & { scope_type: Budget['scope_type']; scope_id: string }) => {
    setSaving(true)
    try {
      await saveBudget(values.scope_type, values.scope_id, month, {
        amount_usd: values.amount_usd, thresholds: values.thresholds, policy: values.policy, enabled: values.enabled
      })
      message.success('预算保存成功')
      setVisible(false)
      mutate()
    } catch { /* 请求拦截器显示错误 */ }
    finally { setSaving(false) }
  }

  const money = (value: string | number) => {
    const n = Number(value)
    return `$${n === 0 ? '0.00' : Math.abs(n) < 0.01 ? n.toFixed(8) : n.toFixed(2)}`
  }
  const columns = [
    { title: '维度', dataIndex: 'scope_type', render: (value: string) => value === 'project' ? '项目' : '部门' },
    { title: '名称', dataIndex: 'scope_name' },
    { title: '月预算', dataIndex: 'amount_usd', render: money },
    { title: '实际消费', dataIndex: 'used_usd', render: money },
    { title: '预扣中', dataIndex: 'reserved_usd', render: money },
    { title: '可用预算', dataIndex: 'remaining_usd', render: money },
    { title: '使用率', dataIndex: 'usage_percent', render: (value: number | null) => value == null ? '—' : `${Number(value).toFixed(2)}%` },
    { title: '告警阈值', dataIndex: 'thresholds', render: (values: number[]) => values.map(t => `${t}%`).join(' / ') },
    { title: '超预算策略', dataIndex: 'policy', render: (value: string) => value === 'block' ? '阻断' : '仅告警' },
    { title: '状态', dataIndex: 'enabled', render: (value: boolean) => <Tag color={value ? 'green' : 'default'}>{value ? '启用' : '停用'}</Tag> },
    { title: '操作', key: 'actions', width: 120, fixed: 'right' as const, render: (_: unknown, row: Budget) => <Button onClick={() => open(row)}>配置</Button> }
  ]
  const reservationColumns = [
    { title: '状态', dataIndex: 'status', width: 90, render: (value: Reservation['status']) => <Tag color={value === 'reserved' ? 'blue' : value === 'committed' ? 'green' : 'default'}>{{ reserved: '预扣中', committed: '已结算', released: '已释放', expired: '已过期' }[value]}</Tag> },
    { title: '用户', dataIndex: 'user_id', width: 150 },
    { title: 'API Key', dataIndex: 'key_id', width: 150 },
    { title: '项目', dataIndex: 'project_id', width: 150, render: (value: string | null) => value || '未归因' },
    { title: '模型', dataIndex: 'model', width: 150 },
    { title: '预估 Token', dataIndex: 'estimated_tokens', width: 120, render: (value: number) => value.toLocaleString() },
    { title: '实际 Token', dataIndex: 'actual_tokens', width: 120, render: (value: number | null) => value == null ? '—' : value.toLocaleString() },
    { title: '预扣金额', dataIndex: 'estimated_cost_usd', width: 120, render: money },
    { title: '实际金额', dataIndex: 'actual_cost_usd', width: 120, render: (value: number | null) => value == null ? '—' : money(value) },
    { title: '创建时间', dataIndex: 'created_at', width: 180, render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm:ss') }
  ]
  const statusMeta = {
    running: { color: 'blue', label: '待处理' }, normal: { color: 'green', label: '正常' },
    abnormal: { color: 'red', label: '异常' }, failed: { color: 'default', label: '失败' },
  }
  const anomalyLabels: Record<string, string> = {
    committed_missing_usage: '已结算缺少用量', committed_usage_mismatch: '结算与用量不一致',
    usage_missing_reservation: '用量缺少预扣', usage_missing_cost: '用量缺少费用',
    expired_lease_still_reserved: '过期租约未释放', terminal_reservation_invalid: '终态预扣无效',
    quota_record_chain_broken: '额度流水断链',
  }
  const reportColumns = [
    { title: '业务日', dataIndex: 'business_date', width: 120 },
    { title: '状态', dataIndex: 'status', width: 100, render: (value: ReconcileReport['status']) => <Tag color={statusMeta[value].color}>{statusMeta[value].label}</Tag> },
    { title: '预扣', dataIndex: 'reservation_count', width: 90 },
    { title: '用量', dataIndex: 'usage_count', width: 90 },
    { title: '额度流水', dataIndex: 'quota_record_count', width: 110 },
    { title: '异常', dataIndex: 'anomaly_count', width: 90 },
    { title: '失败原因', dataIndex: 'error_message', ellipsis: true, render: (value: string | null) => value || '—' },
    { title: '操作', key: 'actions', width: 190, fixed: 'right' as const, render: (_: unknown, row: ReconcileReport) => <Space>
      <Button disabled={!row.anomaly_count} onClick={() => { setSelectedReport(row); setItemPage(1); setAnomalyType(undefined) }}>查看异常</Button>
      <Button loading={rerunning === row.report_id} disabled={!!rerunning || row.status === 'running'} onClick={() => rerun(row)}>重跑</Button>
    </Space> },
  ]
  const itemColumns = [
    { title: '异常类型', dataIndex: 'anomaly_type', width: 170, render: (value: string) => anomalyLabels[value] || value },
    { title: '说明', dataIndex: 'detail', width: 220 },
    { title: '用户', dataIndex: 'user_id', width: 150, render: (value: string | null) => value || '—' },
    { title: '预扣 ID', dataIndex: 'reservation_id', width: 210, render: (value: string | null) => value || '—' },
    { title: '用量 ID', dataIndex: 'usage_log_id', width: 110, render: (value: number | null) => value ?? '—' },
    { title: '额度流水 ID', dataIndex: 'quota_record_id', width: 210, render: (value: string | null) => value || '—' },
    { title: '期望值', dataIndex: 'expected_value', width: 260, ellipsis: true, render: (value: string | null) => value || '—' },
    { title: '实际值', dataIndex: 'actual_value', width: 260, ellipsis: true, render: (value: string | null) => value || '—' },
  ]
  const options = kind === 'project'
    ? (projects?.items || []).map(row => ({ value: row.project_id, label: row.name }))
    : (departments?.items || []).map(row => ({ value: row.dept_id, label: row.name }))
  if (editing && !options.some(option => option.value === editing.scope_id)) {
    options.push({ value: editing.scope_id, label: editing.scope_name })
  }

  return <div style={{ padding: 24 }}>
    <Card title="预算管理" extra={<Space wrap>
      <DatePicker picker="month" allowClear={false} value={dayjs(`${month}-01`)} onChange={value => {
        if (value) setMonth(value.format('YYYY-MM'))
      }} />
      <Button onClick={() => { mutate(); mutateReservations() }}>刷新</Button>
      <Button type="primary" onClick={() => open(null)}>配置月预算</Button>
    </Space>}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }} message="按北京时间自然月配置，金额单位为 USD。项目与部门预算同时生效，可用预算已扣除预扣中金额。未配置或停用时不限制，下月需单独配置。告警每 60 秒检查一次。" />
      {error && <Alert type="error" message="预算加载失败" action={<Button onClick={() => mutate()}>重试</Button>} />}
      <Table rowKey="budget_id" loading={isLoading} dataSource={data?.items || []} columns={columns} scroll={{ x: 1500 }} />
    </Card>
    <Card title="预扣记录" style={{ marginTop: 16 }} extra={<Select allowClear placeholder="全部状态" style={{ width: 140 }} value={reservationStatus} onChange={setReservationStatus} options={[
      { value: 'reserved', label: '预扣中' }, { value: 'committed', label: '已结算' },
      { value: 'released', label: '已释放' }, { value: 'expired', label: '已过期' }
    ]} />}>
      {reservationError && <Alert type="error" message="预扣记录加载失败" action={<Button onClick={() => mutateReservations()}>重试</Button>} />}
      <Table rowKey="reservation_id" loading={reservationsLoading} dataSource={reservationData?.items || []} columns={reservationColumns} scroll={{ x: 1450 }} pagination={{ pageSize: 20 }} />
    </Card>
    <Card title="对账报告" style={{ marginTop: 16 }} extra={<Space>
      <Button onClick={() => mutateReports()}>刷新</Button>
      <Button type="primary" onClick={() => navigate('/admin/dashboard')}>前往导出 CSV</Button>
    </Space>}>
      {reportData && <Alert type="info" showIcon style={{ marginBottom: 16 }} message={
        `按 ${reportData.timezone} 自然日对账，租约宽限 ${reportData.grace_minutes} 分钟，覆盖起点 ${dayjs(reportData.coverage_started_at).format('YYYY-MM-DD HH:mm:ss')}。${reportData.history_rule}。`
      } />}
      {reportError && <Alert type="error" message="对账报告加载失败" action={<Button onClick={() => mutateReports()}>重试</Button>} />}
      <Table rowKey="report_id" loading={reportsLoading} dataSource={reportData?.items || []} columns={reportColumns} scroll={{ x: 1050 }}
        pagination={{ current: reportPage, pageSize: 20, total: reportData?.total || 0, showSizeChanger: false, onChange: setReportPage }} />
      <Typography.Text type="secondary">用量报表导出会沿用管理驾驶舱的日期、部门、项目、用户、Key、模型和渠道筛选，导出期间不阻塞本页操作。</Typography.Text>
    </Card>
    <Modal title={`${month} 月预算配置`} open={visible} onCancel={() => setVisible(false)} onOk={() => form.submit()} confirmLoading={saving}>
      <Form form={form} layout="vertical" onFinish={save}>
        <Form.Item name="scope_type" label="预算维度" rules={[{ required: true }]}>
          <Select disabled={!!editing} onChange={() => form.setFieldValue('scope_id', undefined)} options={[
            { value: 'project', label: '项目' }, { value: 'department', label: '部门' }
          ]} />
        </Form.Item>
        {(kind === 'project' ? projectsError : departmentsError) && <Alert type="error" message="项目或部门加载失败，请刷新后重试" />}
        <Form.Item name="scope_id" label={kind === 'project' ? '项目' : '部门'} rules={[{ required: true, message: '请选择预算归属' }]}>
          <Select disabled={!!editing} showSearch optionFilterProp="label" options={options} />
        </Form.Item>
        <Form.Item name="amount_usd" label="月预算（USD）" rules={[{ required: true, message: '请输入月预算' }]}>
          <InputNumber stringMode min="0" precision={8} style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item name="thresholds" label="告警阈值" rules={[{ required: true, message: '请至少选择一个阈值' }]}>
          <Select mode="multiple" options={Array.from({ length: 100 }, (_, i) => ({ value: i + 1, label: `${i + 1}%` }))} />
        </Form.Item>
        <Form.Item name="policy" label="超预算策略" rules={[{ required: true }]}>
          <Select options={[{ value: 'block', label: '阻断' }, { value: 'alert', label: '仅告警' }]} />
        </Form.Item>
        <Form.Item name="enabled" label="启用预算" valuePropName="checked"><Switch /></Form.Item>
        <Alert type="info" message="预算不足以覆盖本次预扣时，阻断策略会提前拒绝请求。告警按实际消费触发，每个预算阈值仅通知一次；通知负责人和管理员。" />
      </Form>
    </Modal>
    <Drawer title={`${selectedReport?.business_date || ''} 对账异常`} width="min(1100px, 92vw)" open={!!selectedReport} onClose={() => setSelectedReport(null)}
      extra={<Select allowClear placeholder="全部异常类型" style={{ width: 220 }} value={anomalyType} onChange={value => { setAnomalyType(value); setItemPage(1) }}
        options={Object.entries(anomalyLabels).map(([value, label]) => ({ value, label }))} />}>
      {itemError && <Alert type="error" message="异常明细加载失败" />}
      <Table rowKey="item_id" loading={itemsLoading} dataSource={itemData?.items || []} columns={itemColumns} scroll={{ x: 1600 }}
        pagination={{ current: itemPage, pageSize: 20, total: itemData?.total || 0, showSizeChanger: false, onChange: setItemPage }} />
    </Drawer>
  </div>
}

export default Billing
