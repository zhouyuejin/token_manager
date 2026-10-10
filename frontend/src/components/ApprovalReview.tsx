import { useState } from 'react'
import { Alert, Button, Card, Select, Space, Table, Tabs, Tag, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { ApprovalRequest, ApprovalStatus, ApprovalType, decideApproval } from '../api/approvals'
import { useSwrData } from '../hooks/useSwr'
import { useAuthStore } from '../store/auth'
import { useMessage } from '../utils/message'
import { statusColors, statusLabels, summary, typeLabels } from '../utils/approvalPresentation'
import ApprovalDecisionModal from './ApprovalDecisionModal'
import ApprovalDetails from './ApprovalDetails'

type Decision = 'approved' | 'rejected' | 'needs_info'

export default function ApprovalReview({ management = false }: { management?: boolean }) {
  const user = useAuthStore(state => state.user)
  const isAdmin = user?.role === 'admin'
  const message = useMessage()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestId = searchParams.get('request_id')
  const [tab, setTab] = useState('pending')
  const [requestType, setRequestType] = useState<ApprovalType>()
  const [status, setStatus] = useState<ApprovalStatus | undefined>('pending')
  const [requesterId, setRequesterId] = useState<string>()
  const [projectId, setProjectId] = useState<string>()
  const [decisionTarget, setDecisionTarget] = useState<{ request: ApprovalRequest; decision: Decision } | null>(null)
  const { data, error, isLoading, mutate } = useSwrData<ApprovalRequest[]>('/approvals/review', { revalidateOnFocus: true })
  const requests = data || []
  const requesters = [...new Map(requests.map(request => [request.requester_user_id, { value: request.requester_user_id, label: request.requester_name || request.requester_user_id }])).values()]
  const projects = [...new Map(requests.filter(request => ['api_key', 'project_access'].includes(request.request_type) && request.target_id)
    .map(request => [request.target_id!, { value: request.target_id!, label: request.project_name || request.target_id! }])).values()]
  const inTab = (request: ApprovalRequest, key: string) => key === 'processed'
    ? ['approved', 'rejected', 'cancelled'].includes(request.status) : request.status === key
  const records = requests.filter(request => requestId ? request.request_id === requestId :
    (management ? !status || request.status === status : inTab(request, tab)) &&
    (!requestType || request.request_type === requestType) &&
    (!requesterId || request.requester_user_id === requesterId) &&
    (!projectId || (['api_key', 'project_access'].includes(request.request_type) && request.target_id === projectId)))

  const submitDecision = async (request: ApprovalRequest, decision: Decision, comment: string) => {
    await decideApproval(request.request_id, decision, comment)
    message.success(decision === 'approved' ? '申请已通过并生效' : decision === 'rejected' ? '申请已拒绝' : '已通知申请人补充说明')
    setDecisionTarget(null)
    await mutate()
  }

  const columns = [
    { title: '申请人', render: (_: unknown, request: ApprovalRequest) => request.requester_name || request.requester_user_id },
    { title: '申请类型', dataIndex: 'request_type', render: (value: ApprovalType) => typeLabels[value] },
    { title: '申请内容', render: (_: unknown, record: ApprovalRequest) => summary(record) },
    { title: '状态', dataIndex: 'status', render: (value: ApprovalStatus) => <Tag color={statusColors[value]}>{statusLabels[value]}</Tag> },
    { title: '提交时间', dataIndex: 'created_at', render: (value: string) => new Date(value).toLocaleString() },
    { title: '操作', width: 250, fixed: 'right' as const, render: (_: unknown, record: ApprovalRequest) => record.status === 'pending' &&
      (isAdmin || (record.approver_user_id === user?.user_id && record.requester_user_id !== user?.user_id)) ? <Space>
        <Button type="link" onClick={() => setDecisionTarget({ request: record, decision: 'approved' })}>通过</Button>
        <Button type="link" danger onClick={() => setDecisionTarget({ request: record, decision: 'rejected' })}>拒绝</Button>
        <Button type="link" onClick={() => setDecisionTarget({ request: record, decision: 'needs_info' })}>要求补充</Button>
      </Space> : '—' },
  ]

  return <Space direction="vertical" size="large" style={{ width: '100%' }}>
    <Typography.Title level={3} style={{ margin: 0 }}>{management ? '审批管理' : '审批工作台'}</Typography.Title>
    <Alert type="info" showIcon message={isAdmin
      ? management ? '查看全部申请并执行管理员兜底审批。' : '管理员可查看全部待审批申请，并执行兜底审批。'
      : '仅展示指派给您的申请。待补充说明的申请需要申请人提交补充后才能继续审批。'} />
    {requestId && <Alert type="info" showIcon message={`定位申请：${requestId}`} action={<Button size="small" onClick={() => {
      const params = new URLSearchParams(searchParams)
      params.delete('request_id')
      setSearchParams(params, { replace: true })
    }}>返回审批列表</Button>} />}
    <Card>
      <Space wrap>
        <Select allowClear disabled={!!requestId} placeholder="全部申请类型" value={requestType} onChange={setRequestType} style={{ width: 180 }} options={Object.entries(typeLabels).map(([value, label]) => ({ value, label }))} />
        {management && <Select allowClear disabled={!!requestId} placeholder="全部状态" value={status} onChange={setStatus} style={{ width: 180 }} options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} />}
        <Select allowClear disabled={!!requestId} showSearch optionFilterProp="label" placeholder="全部申请人" value={requesterId} onChange={setRequesterId} style={{ width: 200 }} options={requesters} />
        <Select allowClear disabled={!!requestId} showSearch optionFilterProp="label" placeholder="全部项目" value={projectId} onChange={setProjectId} style={{ width: 220 }} options={projects} />
      </Space>
    </Card>
    {error && <Alert type="error" showIcon message="审批记录加载失败，请稍后重试。" />}
    {requestId && data && !records.length && <Alert type="warning" showIcon message="未找到该申请，或您无权查看。" />}
    <Card title={management ? `审批记录（${records.length}）` : undefined}>
      {!management && !requestId && <Tabs activeKey={tab} onChange={setTab} items={[
        { key: 'pending', label: `${isAdmin ? '全部待审批' : '待我审批'}（${requests.filter(request => inTab(request, 'pending')).length}）` },
        { key: 'needs_info', label: `待申请人补充（${requests.filter(request => inTab(request, 'needs_info')).length}）` },
        { key: 'processed', label: '已处理记录' },
      ]} />}
      <Table key={requestId || 'all'} rowKey="request_id" loading={isLoading} dataSource={records} columns={columns} scroll={{ x: 1100 }}
        locale={{ emptyText: requestId ? '未找到申请' : management ? '当前筛选下没有审批记录' : '当前没有符合条件的审批任务' }}
        expandable={{ defaultExpandedRowKeys: requestId ? [requestId] : [], expandedRowRender: record => <ApprovalDetails request={record} /> }} />
    </Card>
    <ApprovalDecisionModal request={decisionTarget?.request || null} decision={decisionTarget?.decision || 'approved'}
      onCancel={() => setDecisionTarget(null)}
      onSubmit={(request, comment) => submitDecision(request, decisionTarget?.decision || 'approved', comment)} />
  </Space>
}
