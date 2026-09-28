import { useState } from 'react'
import { Alert, Card, Descriptions, Select, Space, Table, Tag, Typography } from 'antd'
import { ApprovalRequest, ApprovalStatus, ApprovalType, decideApproval } from '../../api/approvals'
import { ModelGroup } from '../../api/modelGroups'
import { Project } from '../../api/projects'
import { useSwrData, useSwrDataWithParams } from '../../hooks/useSwr'
import { useMessage } from '../../utils/message'
import ApprovalDecisionModal from '../../components/ApprovalDecisionModal'

const typeLabels: Record<ApprovalType, string> = {
  api_key: 'API Key', quota: '额度', model_group: '模型分组', project_access: '项目权限',
}
const statusLabels: Record<ApprovalStatus, string> = {
  pending: '待审批', needs_info: '待补充说明', approved: '已通过并生效', rejected: '已拒绝', cancelled: '已撤回',
}
const statusColors: Record<ApprovalStatus, string> = {
  pending: 'processing', needs_info: 'warning', approved: 'success', rejected: 'error', cancelled: 'default',
}

const formatExpiry = (value: unknown) => value
  ? new Date(String(value)).toLocaleString()
  : '永不过期'

const Approvals = () => {
  const [requestType, setRequestType] = useState<ApprovalType>()
  const [status, setStatus] = useState<ApprovalStatus | undefined>('pending')
  const [requesterId, setRequesterId] = useState<string>()
  const [projectId, setProjectId] = useState<string>()
  const [decisionTarget, setDecisionTarget] = useState<{ request: ApprovalRequest; decision: 'approved' | 'rejected' | 'needs_info' } | null>(null)
  const message = useMessage()
  const params = {
    ...(requestType ? { request_type: requestType } : {}),
    ...(status ? { status } : {}),
    ...(requesterId ? { requester_user_id: requesterId } : {}),
    ...(projectId ? { project_id: projectId } : {}),
  }
  const { data, error, isLoading, mutate } = useSwrDataWithParams<ApprovalRequest[]>('/approvals/review', params)
  const { data: requesters } = useSwrData<{ user_id: string; username: string }[]>('/approvals/review/requesters')
  const { data: projects } = useSwrData<{ items: Project[] }>('/projects/admin')
  const { data: groups } = useSwrData<{ items: ModelGroup[] }>('/admin/model-groups')

  const projectName = (id: unknown) => projects?.items.find(project => project.project_id === id)?.name || String(id || '—')
  const groupName = (id: unknown) => groups?.items.find(group => group.group_id === id)?.name || String(id || '—')
  const requestSummary = (record: ApprovalRequest) => {
    const payload = record.payload
    if (record.request_type === 'quota') return `增加 ${payload.amount} tokens`
    if (record.request_type === 'api_key') return `创建 Key「${payload.name || '—'}」，项目：${projectName(payload.project_id)}`
    if (record.request_type === 'model_group') return `授予模型分组：${groupName(payload.group_id)}`
    return `加入项目：${projectName(payload.project_id || record.target_id)}`
  }

  const submitDecision = async (request: ApprovalRequest, decision: 'approved' | 'rejected' | 'needs_info', comment: string) => {
    await decideApproval(request.request_id, decision, comment)
    message.success(decision === 'approved' ? '申请已通过并生效' : decision === 'rejected' ? '申请已拒绝' : '已通知申请人补充说明')
    setDecisionTarget(null)
    await mutate()
  }

  const columns = [
    { title: '申请人', dataIndex: 'requester_user_id', render: (id: string) => requesters?.find(user => user.user_id === id)?.username || id },
    { title: '类型', dataIndex: 'request_type', render: (value: ApprovalType) => typeLabels[value] },
    { title: '业务影响', render: (_: unknown, record: ApprovalRequest) => requestSummary(record) },
    { title: '状态', dataIndex: 'status', render: (value: ApprovalStatus) => <Tag color={statusColors[value]}>{statusLabels[value]}</Tag> },
    { title: '提交时间', dataIndex: 'created_at', render: (value: string) => new Date(value).toLocaleString() },
    { title: '操作', render: (_: unknown, record: ApprovalRequest) => record.status === 'pending' ? (
      <Space>
        <a onClick={() => setDecisionTarget({ request: record, decision: 'approved' })}>通过</a>
        <a style={{ color: '#ff4d4f' }} onClick={() => setDecisionTarget({ request: record, decision: 'rejected' })}>拒绝</a>
        <a onClick={() => setDecisionTarget({ request: record, decision: 'needs_info' })}>要求补充</a>
      </Space>
    ) : '—' },
  ]

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>审批管理</Typography.Title>
      <Card>
        <Space wrap>
          <Select allowClear placeholder="全部申请类型" value={requestType} onChange={setRequestType} style={{ width: 180 }} options={Object.entries(typeLabels).map(([value, label]) => ({ value, label }))} />
          <Select allowClear placeholder="全部状态" value={status} onChange={setStatus} style={{ width: 180 }} options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} />
          <Select
            allowClear showSearch optionFilterProp="label" placeholder="全部申请人" value={requesterId}
            onChange={setRequesterId} style={{ width: 220 }}
            options={(requesters || []).map(user => ({ value: user.user_id, label: user.username }))}
          />
          <Select
            allowClear showSearch optionFilterProp="label" placeholder="全部项目" value={projectId}
            onChange={setProjectId} style={{ width: 240 }}
            options={(projects?.items || []).map(project => ({ value: project.project_id, label: `${project.department_name} / ${project.name}` }))}
          />
        </Space>
      </Card>
      {error && <Alert type="error" showIcon message="审批记录加载失败，请稍后重试。" />}
      <Card title={`审批记录${data ? `（${data.length}）` : ''}`}>
        <Table
          rowKey="request_id" loading={isLoading} dataSource={data || []} columns={columns}
          expandable={{ expandedRowRender: record => <Descriptions column={1} size="small" items={[
            { key: 'impact', label: '业务影响', children: requestSummary(record) },
            ...(record.request_type === 'api_key' ? [
              { key: 'whitelist', label: 'IP 白名单', children: Array.isArray(record.payload.ip_whitelist) && record.payload.ip_whitelist.length ? record.payload.ip_whitelist.join(', ') : '不限制' },
              { key: 'expiry', label: 'Key 过期时间', children: formatExpiry(record.payload.expires_at) },
            ] : []),
            { key: 'reason', label: '申请理由', children: record.reason },
            { key: 'supplement', label: '补充说明', children: record.supplement || '暂无' },
            { key: 'comment', label: '审批意见', children: record.decision_comment || '暂无' },
            { key: 'time', label: '处理时间', children: record.decided_at ? new Date(record.decided_at).toLocaleString() : '待处理' },
          ]} /> }}
        />
      </Card>
      <ApprovalDecisionModal
        request={decisionTarget?.request || null}
        decision={decisionTarget?.decision || 'approved'}
        onCancel={() => setDecisionTarget(null)}
        onSubmit={(request, comment) => submitDecision(request, decisionTarget?.decision || 'approved', comment)}
      />
    </Space>
  )
}

export default Approvals
