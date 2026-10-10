import { useState } from 'react'
import { Alert, Button, Card, Input, Modal, Select, Space, Table, Tag, Typography } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { ApprovalRequest, ApprovalStatus, ApprovalType, cancelApproval, claimApprovalKey, supplementApproval } from '../api/approvals'
import { useSwrData } from '../hooks/useSwr'
import { useMessage } from '../utils/message'
import { effectSummary, statusColors, statusLabels, summary, typeLabels } from '../utils/approvalPresentation'
import ApplicationModal from '../components/ApplicationModal'
import ApprovalDetails from '../components/ApprovalDetails'

export default function Applications() {
  const message = useMessage()
  const [searchParams, setSearchParams] = useSearchParams()
  const requestId = searchParams.get('request_id')
  const { data: mine, error, isLoading, mutate } = useSwrData<ApprovalRequest[]>('/approvals/mine', { revalidateOnFocus: true })
  const [createOpen, setCreateOpen] = useState(false)
  const [requestType, setRequestType] = useState<ApprovalType>()
  const [status, setStatus] = useState<ApprovalStatus>()
  const [supplementTarget, setSupplementTarget] = useState<ApprovalRequest | null>(null)
  const [supplementText, setSupplementText] = useState('')
  const [supplementing, setSupplementing] = useState(false)
  const [claimingId, setClaimingId] = useState<string | null>(null)
  const [secret, setSecret] = useState<{ key_id: string; api_key: string } | null>(null)
  const records = (mine || []).filter(request => requestId ? request.request_id === requestId :
    (!requestType || request.request_type === requestType) && (!status || request.status === status))
  const needsInfoCount = (mine || []).filter(request => request.status === 'needs_info').length

  const clearLocation = () => {
    const params = new URLSearchParams(searchParams)
    params.delete('request_id')
    setSearchParams(params, { replace: true })
  }

  const cancelRequest = (request: ApprovalRequest) => Modal.confirm({
    title: '撤回申请', content: '撤回后本申请不会继续审批，确定撤回吗？', okText: '确认撤回', cancelText: '返回',
    okButtonProps: { danger: true },
    onOk: async () => {
      await cancelApproval(request.request_id)
      message.success('申请已撤回')
      await mutate()
    },
  })

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
      await mutate()
    } finally { setSupplementing(false) }
  }

  const claimKey = async (request: ApprovalRequest) => {
    setClaimingId(request.request_id)
    try {
      const result = await claimApprovalKey(request.request_id)
      setSecret(result)
      await mutate()
    } catch {
      // 请求错误由统一拦截器提示；刷新领取状态以处理其他窗口已领取的情况。
      await mutate()
    } finally { setClaimingId(null) }
  }

  const columns = [
    { title: '申请类型', dataIndex: 'request_type', render: (value: ApprovalType) => typeLabels[value] },
    { title: '申请内容', render: (_: unknown, record: ApprovalRequest) => summary(record) },
    { title: '状态', dataIndex: 'status', render: (value: ApprovalStatus) => <Tag color={statusColors[value]}>{statusLabels[value]}</Tag> },
    { title: '审批意见', dataIndex: 'decision_comment', render: (value: string | null) => value || '—', ellipsis: true },
    { title: '生效结果', render: (_: unknown, record: ApprovalRequest) => effectSummary(record) },
    { title: '提交时间', dataIndex: 'created_at', render: (value: string) => new Date(value).toLocaleString() },
    { title: '操作', width: 190, fixed: 'right' as const, render: (_: unknown, record: ApprovalRequest) => <Space>
      {record.status === 'needs_info' && <Button type="link" onClick={() => { setSupplementTarget(record); setSupplementText('') }}>补充说明</Button>}
      {['pending', 'needs_info'].includes(record.status) && <Button danger type="link" onClick={() => cancelRequest(record)}>撤回</Button>}
      {record.secret_available && <Button type="link" loading={claimingId === record.request_id} disabled={!!claimingId || !!secret} onClick={() => claimKey(record)}>领取 Key</Button>}
    </Space> },
  ]

  return <Space direction="vertical" size="large" style={{ width: '100%' }}>
    <Space style={{ width: '100%', justifyContent: 'space-between' }}>
      <Typography.Title level={3} style={{ margin: 0 }}>我的申请</Typography.Title>
      <Button type="primary" onClick={() => setCreateOpen(true)}>新建申请</Button>
    </Space>
    <Alert type="info" showIcon message="申请通过后生效。API Key 请在对应申请中点击“领取 Key”，明文仅提供一次。" />
    {!!needsInfoCount && <Alert type="warning" showIcon message={`有 ${needsInfoCount} 条申请需要补充说明`} action={<Button size="small" onClick={() => { clearLocation(); setRequestType(undefined); setStatus('needs_info') }}>查看待补充</Button>} />}
    {requestId && <Alert type="info" showIcon message={`定位申请：${requestId}`} action={<Button size="small" onClick={clearLocation}>返回全部申请</Button>} />}
    <Card>
      <Space wrap>
        <Select allowClear disabled={!!requestId} placeholder="全部申请类型" value={requestType} onChange={setRequestType} style={{ width: 180 }} options={Object.entries(typeLabels).map(([value, label]) => ({ value, label }))} />
        <Select allowClear disabled={!!requestId} placeholder="全部状态" value={status} onChange={setStatus} style={{ width: 180 }} options={Object.entries(statusLabels).map(([value, label]) => ({ value, label }))} />
      </Space>
    </Card>
    {error && <Alert type="error" showIcon message="申请记录加载失败，请稍后重试。" />}
    {requestId && mine && !records.length && <Alert type="warning" showIcon message="未找到该申请，或您无权查看。" />}
    <Card title={`申请记录（${records.length}）`}>
      <Table key={requestId || 'all'} rowKey="request_id" loading={isLoading} dataSource={records} columns={columns} scroll={{ x: 1100 }}
        expandable={{ defaultExpandedRowKeys: requestId ? [requestId] : [], expandedRowRender: record => <ApprovalDetails request={record} /> }} />
    </Card>
    <ApplicationModal open={createOpen} onCancel={() => setCreateOpen(false)} onSubmitted={async request => {
      setCreateOpen(false)
      setSearchParams({ request_id: request.request_id })
      await mutate()
    }} />
    <Modal open={!!supplementTarget} title="补充申请说明" okText="提交补充" confirmLoading={supplementing}
      onCancel={() => setSupplementTarget(null)} onOk={submitSupplement}>
      <Typography.Paragraph>审批人要求：{supplementTarget?.decision_comment || '请补充申请说明'}</Typography.Paragraph>
      <Input.TextArea value={supplementText} onChange={event => setSupplementText(event.target.value)} rows={4} maxLength={1000} showCount style={{ marginBottom: 24 }} />
    </Modal>
    <Modal open={!!secret} title={`新 API Key（${secret?.key_id || ''}）`} closable={false} maskClosable={false} keyboard={false} footer={[
      <Button key="copy" type="primary" onClick={async () => {
        try {
          if (secret) await navigator.clipboard.writeText(secret.api_key)
          message.success('已复制 API Key')
        } catch { message.error('复制失败，请手动复制保存。') }
      }}>复制 Key</Button>,
      <Button key="close" onClick={() => setSecret(null)}>我已保存</Button>,
    ]}>
      <Alert type="warning" showIcon message="请立即复制保存，关闭后无法再次领取完整 Key。" style={{ marginBottom: 12 }} />
      <Input.TextArea value={secret?.api_key || ''} readOnly autoSize />
    </Modal>
  </Space>
}
