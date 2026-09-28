import { useEffect, useState } from 'react'
import { Alert, Button, Card, DatePicker, Descriptions, Empty, Form, Input, InputNumber, Modal, Select, Space, Spin, Table, Tabs, Tag, Typography } from 'antd'
import dayjs, { Dayjs } from 'dayjs'
import { ApprovalRequest, ApprovalStatus, ApprovalType, ModelGroupApplicationOption, ProjectAccessOption, cancelApproval, createApiKeyApplication, createModelGroupApplication, createProjectAccessApplication, createQuotaApplication, decideApproval } from '../api/approvals'
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
  pending: '待审批', approved: '已通过并生效', rejected: '已拒绝', cancelled: '已撤回',
}
const statusColors: Record<ApprovalStatus, string> = {
  pending: 'processing', approved: 'success', rejected: 'error', cancelled: 'default',
}

const summary = (request: ApprovalRequest) => {
  const payload = request.payload
  if (request.request_type === 'quota') return `申请增加 ${payload.amount} tokens`
  if (request.request_type === 'api_key') return `用途：${payload.name || '—'}；项目：${payload.project_id || request.target_id || '—'}`
  if (request.request_type === 'model_group') return `申请模型分组：${payload.group_id || request.target_id || '—'}`
  return `申请加入项目：${payload.project_id || request.target_id || '—'}`
}

const Approvals = () => {
  const [form] = Form.useForm<ApplicationValues>()
  const user = useAuthStore(state => state.user)
  const message = useMessage()
  const type = Form.useWatch('request_type', form) || 'api_key'
  const { data: mine, error: mineError, isLoading: mineLoading, mutate: mutateMine } = useSwrData<ApprovalRequest[]>('/approvals/mine', { revalidateOnFocus: true })
  const { data: assigned, error: assignedError, isLoading: assignedLoading, mutate: mutateAssigned } = useSwrData<ApprovalRequest[]>('/approvals/review?status=pending')
  const { data: projects } = useSwrData<{ items: Project[] }>('/projects')
  const { data: accessOptions, error: accessOptionsError } = useSwrData<ProjectAccessOption[]>('/approvals/project-access/options')
  const { data: groupOptions, error: groupOptionsError } = useSwrData<ModelGroupApplicationOption[]>('/approvals/model-group/options')
  const [submitting, setSubmitting] = useState(false)
  const [decisionTarget, setDecisionTarget] = useState<{ request: ApprovalRequest; decision: 'approved' | 'rejected' } | null>(null)
  const [secret, setSecret] = useState<string | null>(null)

  useEffect(() => {
    form.resetFields(['project_id', 'name', 'ip_whitelist', 'expires_at', 'amount', 'group_id'])
  }, [form, type])

  useEffect(() => {
    const key = mine?.find(request => request.result?.api_key)?.result?.api_key
    if (key) setSecret(key)
  }, [mine])

  const submitApplication = async (values: ApplicationValues) => {
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

  const submitDecision = async (request: ApprovalRequest, decision: 'approved' | 'rejected', comment: string) => {
    await decideApproval(request.request_id, decision, comment)
    message.success(decision === 'approved' ? '申请已通过并生效' : '申请已拒绝')
    setDecisionTarget(null)
    await Promise.all([mutateMine(), mutateAssigned()])
  }

  const applicationColumns = [
    { title: '申请类型', dataIndex: 'request_type', render: (value: ApprovalType) => typeLabels[value] },
    { title: '申请内容', render: (_: unknown, record: ApprovalRequest) => summary(record) },
    { title: '状态', dataIndex: 'status', render: (value: ApprovalStatus) => <Tag color={statusColors[value]}>{statusLabels[value]}</Tag> },
    { title: '提交时间', dataIndex: 'created_at', render: (value: string) => new Date(value).toLocaleString() },
    { title: '操作', render: (_: unknown, record: ApprovalRequest) => record.status === 'pending'
      ? <Button danger type="link" onClick={() => cancelRequest(record)}>撤回</Button> : '—' },
  ]
  const reviewColumns = [
    { title: '申请人', dataIndex: 'requester_user_id' },
    { title: '申请类型', dataIndex: 'request_type', render: (value: ApprovalType) => typeLabels[value] },
    { title: '业务影响', render: (_: unknown, record: ApprovalRequest) => summary(record) },
    { title: '理由', dataIndex: 'reason', ellipsis: true },
    { title: '提交时间', dataIndex: 'created_at', render: (value: string) => new Date(value).toLocaleString() },
    { title: '操作', render: (_: unknown, record: ApprovalRequest) => <Space>
      <Button type="primary" onClick={() => setDecisionTarget({ request: record, decision: 'approved' })}>通过</Button>
      <Button danger onClick={() => setDecisionTarget({ request: record, decision: 'rejected' })}>拒绝</Button>
    </Space> },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>自助申请与审批</Typography.Title>
      <Alert type="info" showIcon message="申请在审批通过前不会生效；API Key 明文仅在首次查看时展示，请及时复制保存。" />
      <Card title="提交申请">
        {user?.quota < 0 && <Alert type="info" showIcon style={{ marginBottom: 16 }} message="当前账号为无限额度，无需提交额度申请。" />}
        <Form form={form} layout="vertical" initialValues={{ request_type: 'api_key' }} onFinish={submitApplication}>
          <Form.Item name="request_type" label="申请类型" rules={[{ required: true }]}>
            <Select options={[
              { value: 'api_key', label: 'API Key' },
              ...(user?.quota >= 0 ? [{ value: 'quota', label: '额度' }] : []),
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
          <Button type="primary" htmlType="submit" loading={submitting}>提交申请</Button>
        </Form>
      </Card>

      <Tabs items={[
        { key: 'mine', label: '我的申请', children: mineError
          ? <Alert type="error" showIcon message="申请记录加载失败，请稍后重试。" />
          : <Table rowKey="request_id" loading={mineLoading} dataSource={mine || []} columns={applicationColumns}
              expandable={{ expandedRowRender: record => <Descriptions column={1} size="small" items={[
                { key: 'reason', label: '申请理由', children: record.reason },
                { key: 'comment', label: '审批意见', children: record.decision_comment || '暂无' },
                { key: 'effect', label: '生效结果', children: record.status === 'approved' ? '已按申请内容生效' : '待审批通过后生效' },
              ]} /> }} /> },
        { key: 'review', label: `待我审批${assigned?.length ? ` (${assigned.length})` : ''}`, children: assignedError
          ? <Alert type="error" showIcon message="待审批列表加载失败，请稍后重试。" />
          : assignedLoading ? <Spin /> : (assigned || []).length === 0 ? <Empty description="当前没有指派给您的待审批申请" />
          : <Table rowKey="request_id" dataSource={assigned || []} columns={reviewColumns} /> },
      ]} />

      <ApprovalDecisionModal
        request={decisionTarget?.request || null}
        decision={decisionTarget?.decision || 'approved'}
        onCancel={() => setDecisionTarget(null)}
        onSubmit={(request, comment) => submitDecision(request, decisionTarget?.decision || 'approved', comment)}
      />
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
