import { ApprovalRequest, ApprovalStatus, ApprovalType } from '../api/approvals'
import { Project } from '../api/projects'

export const typeLabels: Record<ApprovalType, string> = {
  api_key: 'API Key 申请', quota: '额度申请', model_group: '模型访问申请', project_access: '加入项目申请',
}
export const statusLabels: Record<ApprovalStatus, string> = {
  pending: '待审批', needs_info: '待补充说明', approved: '已通过并生效', rejected: '已拒绝', cancelled: '已撤回',
}
export const statusColors: Record<ApprovalStatus, string> = {
  pending: 'processing', needs_info: 'warning', approved: 'success', rejected: 'error', cancelled: 'default',
}

export const summary = (request: ApprovalRequest, projects: Pick<Project, 'project_id' | 'name'>[] = []) => {
  const payload = request.payload
  const projectId = payload.project_id || request.target_id
  const projectName = request.project_name || projects.find(project => project.project_id === projectId)?.name || projectId || '—'
  if (request.request_type === 'quota') return `申请增加 ${payload.amount} tokens`
  if (request.request_type === 'api_key') return `用途：${payload.name || '—'}；项目：${projectName}`
  if (request.request_type === 'model_group') return `申请模型分组：${request.model_group_name || payload.group_id || request.target_id || '—'}`
  return `申请加入项目：${projectName}`
}

export const effectSummary = (request: ApprovalRequest) => {
  if (request.status === 'pending') return '待审批，通过后才会生效'
  if (request.status === 'needs_info') return '待补充说明，尚未生效'
  if (request.status === 'rejected') return '未生效：申请已拒绝'
  if (request.status === 'cancelled') return '未生效：申请已撤回'
  if (request.request_type === 'quota') return `已增加 ${request.payload.amount} tokens`
  if (request.request_type === 'api_key') return request.secret_available ? '已创建 Key，待领取' : '已创建 Key；明文已领取或不可领取'
  if (request.request_type === 'model_group') return '已授予申请的模型分组权限'
  return '已加入申请的项目'
}

