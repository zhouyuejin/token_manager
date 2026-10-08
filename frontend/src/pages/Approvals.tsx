import { useEffect, useState } from 'react'
import { Alert, Button, Card, DatePicker, Descriptions, Empty, Form, Input, InputNumber, Modal, Select, Space, Spin, Table, Tabs, Tag, Typography } from 'antd'
import dayjs, { Dayjs } from 'dayjs'
import { ApprovalRequest, ApprovalStatus, ApprovalType, ModelGroupApplicationOption, ProjectAccessOption, cancelApproval, createApiKeyApplication, createModelGroupApplication, createProjectAccessApplication, createQuotaApplication, decideApproval, supplementApproval } from '../api/approvals'
import { Project } from '../api/projects'
import { useAuthStore } from '../store/auth'
import { useSwrData } from '../hooks/useSwr'
import { parseApiKeyWhitelist } from '../utils/apiKeyWhitelist'
import { useMessage } from '../utils/message'
import ApprovalDecisionModal from '../components/ApprovalDecisionModal'

type ApplicationValues = {
  request_type: ApprovalType
  project_id?: string
  name?: string
  ip_whitelist?: string
  expires_at?: Dayjs | null
  amount?: number
  group_id?: string
  reason: string
}

const typeLabels: Record<ApprovalType, string> = {
  api_key: 'API Key', quota: '额度', model_group: '模型分组', project_access: '项目权限',
}
const statusLabels: Record<ApprovalStatus, string> = {
  pending: '待审批', needs_info: '待补充说明', approved: '已通过并生效', rejected: '已拒绝', cancelled: '已撤回',
}
const statusColors: Record<ApprovalStatus, string> = {
  pending: 'processing', needs_info: 'warning', approved: 'success', rejected: 'error', cancelled: 'default',
}

const summary = (request: ApprovalRequest, projects: Pick<Project, 'project_id' | 'name'>[]) => {
  const payload = request.payload
  const projectId = payload.project_id || request.target_id
  const projectName = projects.find(project => project.project_id === projectId)?.name || projectId || '—'
  if (request.request_type === 'quota') return `申请增加 ${payload.amount} tokens`
  if (request.request_type === 'api_key') return `用途：${payload.name || '—'}；项目：${projectName}`
  if (request.request_type === 'model_group') return `申请模型分组：${payload.group_id || request.target_id || '—'}`
  return `申请加入项目：${projectName}`
}

const effectSummary = (request: ApprovalRequest) => {
  if (request.status === 'pending') return '待审批，通过后才会生效'
  if (request.status === 'needs_info') return '待补充说明，尚未生效'
  if (request.status === 'rejected') return '未生效：申请已拒绝'
  if (request.status === 'cancelled') return '未生效：申请已撤回'
  if (request.request_type === 'quota') return `已增加 ${request.payload.amount} tokens`
  if (request.request_type === 'api_key') return request.result?.key_id
    ? `已创建 Key（${request.result.key_id}）`
    : '已创建 Key；完整 Key 明文仅展示一次'
  if (request.request_type === 'model_group') return '已授予申请的模型分组权限'
  return '已加入申请的项目'
}

const Approvals = () => {
  const [form] = Form.useForm<ApplicationValues>()
  const user = useAuthStore(state => state.user)
  const message = useMessage()
  const type = Form.useWatch('request_type', form) || 'api_key'
  const quotaApplicationBlocked = type === 'quota' && user?.quota < 0
  const { data: mine, error: mineError, isLoading: mineLoading, mutate: mutateMine } = useSwrData<ApprovalRequest[]>('/approvals/mine', { revalidateOnFocus: true })
  const { data: assigned, error: assignedError, isLoading: assignedLoading, mutate: mutateAssigned } = useSwrData<ApprovalRequest[]>('/approvals/review?status=pending')
  const { data: projects } = useSwrData<{ items: Project[] }>('/projects')
  const { data: accessOptions, error: accessOptionsError } = useSwrData<ProjectAccessOption[]>('/approvals/project-access/options')
  const { data: groupOptions, error: groupOptionsError } = useSwrData<ModelGroupApplicationOption[]>('/approvals/model-group/options')
  const summaryProjects = [...(projects?.items || []), ...(accessOptions || [])]
  const [submitting, setSubmitting] = useState(false)
  const [decisionTarget, setDecisionTarget] = useState<{ request: ApprovalRequest; decision: 'approved' | 'rejected' | 'needs_info' } | null>(null)
  const [supplementTarget, setSupplementTarget] = useState<ApprovalRequest | null>(null)
  const [supplementText, setSupplementText] = useState('')
  const [supplementing, setSupplementing] = useState(false)
  const [secret, setSecret] = useState<string | null>(null)

  useEffect(() => {
    form.resetFields(['project_id', 'name', 'ip_whitelist', 'expires_at', 'amount', 'group_id'])
  }, [form, type])

  useEffect(() => {
    const key = mine?.find(request => request.result?.api_key)?.result?.api_key
    if (key) setSecret(key)
  }, [mine])

  const submitApplication = async (values: ApplicationValues) => {
    if (values.request_type === 'quota' && user?.quota < 0) {
      message.info('当前账号为无限额度，无需提交额度申请。')
      return
    }
    setSubmitting(true)
    try {
      if (values.request_type === 'api_key') {
        await createApiKeyApplication({
          project_id: values.project_id!, name: values.name!.trim(),
          ip_whitelist: parseApiKeyWhitelist(values.ip_whitelist || ''),
          expires_at: values.expires_at?.toISOString() || null, reason: values.reason.trim(),
        })
      } else if (values.request_type === 'quota') {
        await createQuotaApplication({ amount: values.amount!, reason: values.reason.trim() })
      } else if (values.request_type === 'model_group') {
        await createModelGroupApplication({ group_id: values.group_id!, reason: values.reason.trim() })
      } else {
        await createProjectAccessApplication({ project_id: values.project_id!, reason: values.reason.trim() })
      }
      message.success('申请已提交，审批通过前不会生效')
      form.resetFields()
      form.setFieldValue('request_type', values.request_type)
      await Promise.all([mutateMine(), mutateAssigned()])
    } finally {
      setSubmitting(false)
    }
  }

  const cancelRequest = (request: ApprovalRequest) => {
    Modal.confirm({
      title: '撤回申请', content: '撤回后本申请不会继续审批，确定撤回吗？', okText: '确认撤回',
      cancelText: '返回', okButtonProps: { danger: true },
      onOk: async () => {
        await cancelApproval(request.request_id)
        message.success('申请已撤回')
        await Promise.all([mutateMine(), mutateAssigned()])
      },
    })
  }

  const submitSupplement = async () => {
    if (!supplementTarget || !supplementText.trim()) {
      message.error('请填写补充说明')
      return
    }
    setSupplementing(true)
    try {
      await supplementApproval(supplementTarget.request_id, supplementText.trim())
      message.success('补充说明已提交，申请重新进入待审批')
      setSupplementTarget(null)
      setSupplementText('')
      await mutateMine()
    } finally {
      setSupplementing(false)
    }
  }

  const submitDecision = async (request: ApprovalRequest, decision: 'approved' | 'rejected' | 'needs_info', comment: string) => {
    await decideApproval(request.request_id, decision, comment)
    message.success(decision === 'approved' ? '申请已通过并生效' : decision === 'rejected' ? '申请已拒绝' : '已通知申请人补充说明')
    setDecisionTarget(null)
    await Promise.all([mutateMine(), mutateAssigned()])
  }

  const applicationColumns = [
    { title: '申请类型', dataIndex: 'request_type', render: (value: ApprovalType) => typeLabels[value] },
    { title: '申请内容', render: (_: unknown, record: ApprovalRequest) => summary(record, summaryProjects) },
    { title: '状态', dataIndex: 'status', render: (value: ApprovalStatus) => <Tag color={statusColors[value]}>{statusLabels[value]}</Tag> },
    { title: '审批意见', dataIndex: 'decision_comment', render: (value: string | null) => value || '—', ellipsis: true },
    { title: '生效结果', render: (_: unknown, record: ApprovalRequest) => effectSummary(record) },
    { title: '提交时间', dataIndex: 'created_at', render: (value: string) => new Date(value).toLocaleString() },
    { title: '操作', render: (_: unknown, record: ApprovalRequest) => record.status === 'pending' || record.status === 'needs_info'
      ? <Space>
          {record.status === 'needs_info' && <Button type="link" onClick={() => { setSupplementTarget(record); setSupplementText('') }}>补充说明</Button>}
          <Button danger type="link" onClick={() => cancelRequest(record)}>撤回</Button>
        </Space> : '—' },
  ]
  const reviewColumns = [
    { title: '申请人', dataIndex: 'requester_user_id' },
    { title: '申请类型', dataIndex: 'request_type', render: (value: ApprovalType) => typeLabels[value] },
    { title: '业务影响', render: (_: unknown, record: ApprovalRequest) => summary(record, summaryProjects) },
    { title: '理由', dataIndex: 'reason', ellipsis: true },
    { title: '补充说明', dataIndex: 'supplement', render: (value: string | null) => value || '—', ellipsis: true },
    { title: '提交时间', dataIndex: 'created_at', render: (value: string) => new Date(value).toLocaleString() },
    { title: '操作', width: 300, fixed: 'right' as const, render: (_: unknown, record: ApprovalRequest) => <Space style={{ whiteSpace: 'nowrap' }}>
      <Button type="primary" onClick={() => setDecisionTarget({ request: record, decision: 'approved' })}>通过</Button>
      <Button danger onClick={() => setDecisionTarget({ request: record, decision: 'rejected' })}>拒绝</Button>
      <Button onClick={() => setDecisionTarget({ request: record, decision: 'needs_info' })}>要求补充</Button>
    </Space> },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>自助申请与审批</Typography.Title>
      <Alert type="info" showIcon message="申请在审批通过前不会生效；API Key 明文仅在首次查看时展示，请及时复制保存。" />
      <Card title="提交申请">
        {quotaApplicationBlocked && <Alert type="info" showIcon style={{ marginBottom: 16 }} message="当前账号为无限额度，无需提交额度申请。" />}
        <Form form={form} layout="vertical" initialValues={{ request_type: 'api_key' }} onFinish={submitApplication}>
          <Form.Item name="request_type" label="申请类型" rules={[{ required: true }]}>
            <Select options={[
              { value: 'api_key', label: 'API Key' },
              { value: 'quota', label: user?.quota < 0 ? '额度（当前账号为无限额度，无需申请）' : '额度', disabled: !user || user.quota < 0 },
              { value: 'model_group', label: '模型分组权限' },
              { value: 'project_access', label: '加入项目' },
            ]} />
          </Form.Item>
          {type === 'api_key' && <>
            <Form.Item name="project_id" label="项目" rules={[{ required: true, message: '请选择项目' }]}>
              <Select loading={!projects} options={(projects?.items || []).map(project => ({ value: project.project_id, label: `${project.department_name} / ${project.name}` }))} />
            </Form.Item>
            <Form.Item name="name" label="用途" rules={[{ required: true, whitespace: true, message: '请填写用途' }]}>
              <Input maxLength={100} placeholder="例如：生产环境服务" />
            </Form.Item>
            <Form.Item name="ip_whitelist" label="IP 白名单" extra="每行一个 IP，也可用逗号分隔；留空表示不限制。">
              <Input.TextArea rows={2} placeholder="203.0.113.10" />
            </Form.Item>
            <Form.Item name="expires_at" label="过期时间（可选）">
              <DatePicker showTime style={{ width: '100%' }} disabledDate={date => date.isBefore(dayjs().startOf('day'))} />
            </Form.Item>
          </>}
          {type === 'quota' && <Form.Item name="amount" label="申请额度（tokens）" rules={[{ required: true, message: '请输入申请额度' }]}>
            <InputNumber min={1} precision={0} style={{ width: '100%' }} />
          </Form.Item>}
          {type === 'model_group' && <Form.Item name="group_id" label="模型分组" rules={[{ required: true, message: '请选择模型分组' }]}>
            <Select loading={!groupOptions} options={(groupOptions || []).map(group => ({ value: group.group_id, label: group.name }))} />
          </Form.Item>}
          {type === 'project_access' && <Form.Item name="project_id" label="申请加入的项目" rules={[{ required: true, message: '请选择项目' }]}>
            <Select loading={!accessOptions} options={(accessOptions || []).map(project => ({ value: project.project_id, label: `${project.department_name} / ${project.name}` }))} />
          </Form.Item>}
          {accessOptionsError && type === 'project_access' && <Alert type="error" showIcon message="项目列表加载失败，请稍后重试。" />}
          {groupOptionsError && type === 'model_group' && <Alert type="error" showIcon message="模型分组加载失败，请稍后重试。" />}
          <Form.Item name="reason" label="申请理由" rules={[{ required: true, whitespace: true, message: '请填写申请理由' }]}>
            <Input.TextArea rows={3} maxLength={1000} showCount />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting} disabled={quotaApplicationBlocked}>提交申请</Button>
        </Form>
      </Card>

      <Tabs items={[
        { key: 'mine', label: '我的申请', children: mineError
          ? <Alert type="error" showIcon message="申请记录加载失败，请稍后重试。" />
          : <Table rowKey="request_id" loading={mineLoading} dataSource={mine || []} columns={applicationColumns}
              expandable={{ expandedRowRender: record => <Descriptions column={1} size="small" items={[
                { key: 'reason', label: '申请理由', children: record.reason },
                { key: 'comment', label: '审批意见', children: record.decision_comment || '暂无' },
                { key: 'supplement', label: '补充说明', children: record.supplement || '暂无' },
                { key: 'effect', label: '生效结果', children: effectSummary(record) },
              ]} /> }} /> },
        { key: 'review', label: `待我审批${assigned?.length ? ` (${assigned.length})` : ''}`, children: assignedError
          ? <Alert type="error" showIcon message="待审批列表加载失败，请稍后重试。" />
          : assignedLoading ? <Spin /> : (assigned || []).length === 0 ? <Empty description="当前没有指派给您的待审批申请" />
          : <Table rowKey="request_id" dataSource={assigned || []} columns={reviewColumns} scroll={{ x: 1300 }} /> },
      ]} />

      <ApprovalDecisionModal
        request={decisionTarget?.request || null}
        decision={decisionTarget?.decision || 'approved'}
        onCancel={() => setDecisionTarget(null)}
        onSubmit={(request, comment) => submitDecision(request, decisionTarget?.decision || 'approved', comment)}
      />
      <Modal
        open={!!supplementTarget} title="补充申请说明" okText="提交补充" okButtonProps={{ loading: supplementing }}
        onCancel={() => setSupplementTarget(null)} onOk={submitSupplement}
      >
        <Typography.Paragraph>审批人要求：{supplementTarget?.decision_comment || '请补充申请说明'}</Typography.Paragraph>
        <Input.TextArea value={supplementText} onChange={event => setSupplementText(event.target.value)} rows={4} maxLength={1000} showCount />
      </Modal>
      <Modal open={!!secret} title="新 API Key（仅展示一次）" onCancel={() => setSecret(null)} footer={[
        <Button key="copy" type="primary" onClick={async () => {
          if (secret) await navigator.clipboard.writeText(secret)
          message.success('已复制 API Key')
        }}>复制 Key</Button>,
        <Button key="close" onClick={() => setSecret(null)}>关闭</Button>,
      ]}>
        <Alert type="warning" showIcon message="请立即复制保存，离开后无法再次查看完整 Key。" style={{ marginBottom: 12 }} />
        <Input.TextArea value={secret || ''} readOnly autoSize />
      </Modal>
    </Space>
  )
}

export default Approvals
