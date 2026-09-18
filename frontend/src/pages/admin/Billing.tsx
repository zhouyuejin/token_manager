import { useState } from 'react'
import { Alert, Button, Card, DatePicker, Form, InputNumber, Modal, Select, Space, Switch, Table, Tag } from 'antd'
import dayjs from 'dayjs'
import { Budget, BudgetSave, saveBudget } from '../../api/billing'
import { Department, Project } from '../../api/projects'
import { useSwrData, useSwrDataWithParams } from '../../hooks/useSwr'
import { useMessage } from '../../utils/message'

const Billing = () => {
  const [month, setMonth] = useState(() => new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit'
  }).format(new Date()))
  const { data, error, isLoading, mutate } = useSwrDataWithParams<{ items: Budget[] }>('/admin/billing/budgets', { month })
  const { data: projects, error: projectsError } = useSwrData<{ items: Project[] }>('/projects/admin')
  const { data: departments, error: departmentsError } = useSwrData<{ items: Department[] }>('/projects/admin/departments')
  const [visible, setVisible] = useState(false)
  const [editing, setEditing] = useState<Budget | null>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()
  const kind: Budget['scope_type'] = Form.useWatch('scope_type', form) || 'project'
  const message = useMessage()

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
      <Button onClick={() => mutate()}>刷新</Button>
      <Button type="primary" onClick={() => open(null)}>配置月预算</Button>
    </Space>}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }} message="按北京时间自然月配置，金额单位为 USD。项目与部门预算同时生效，可用预算已扣除预扣中金额。未配置或停用时不限制，下月需单独配置。告警每 60 秒检查一次。" />
      {error && <Alert type="error" message="预算加载失败" action={<Button onClick={() => mutate()}>重试</Button>} />}
      <Table rowKey="budget_id" loading={isLoading} dataSource={data?.items || []} columns={columns} scroll={{ x: 1500 }} />
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
  </div>
}

export default Billing
