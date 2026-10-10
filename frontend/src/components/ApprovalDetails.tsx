import { Descriptions } from 'antd'
import { ApprovalRequest } from '../api/approvals'
import { effectSummary, summary } from '../utils/approvalPresentation'

export default function ApprovalDetails({ request }: { request: ApprovalRequest }) {
  return <Descriptions column={1} size="small" items={[
    { key: 'id', label: '申请编号', children: request.request_id },
    { key: 'impact', label: '申请内容', children: summary(request) },
    ...(request.request_type === 'api_key' ? [
      { key: 'whitelist', label: 'IP 白名单', children: Array.isArray(request.payload.ip_whitelist) && request.payload.ip_whitelist.length ? request.payload.ip_whitelist.join(', ') : '不限制' },
      { key: 'expiry', label: 'Key 过期时间', children: request.payload.expires_at ? new Date(String(request.payload.expires_at)).toLocaleString() : '永不过期' },
    ] : []),
    { key: 'reason', label: '申请理由', children: request.reason },
    { key: 'supplement', label: '补充说明', children: request.supplement || '暂无' },
    { key: 'comment', label: '审批意见', children: request.decision_comment || '暂无' },
    { key: 'effect', label: '生效结果', children: effectSummary(request) },
    { key: 'time', label: '处理时间', children: request.decided_at ? new Date(request.decided_at).toLocaleString() : '—' },
  ]} />
}
