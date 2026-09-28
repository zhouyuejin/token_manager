import { get, post } from './request'

export type ApprovalType = 'api_key' | 'quota' | 'model_group' | 'project_access'
export type ApprovalStatus = 'pending' | 'needs_info' | 'approved' | 'rejected' | 'cancelled'

export interface ApprovalRequest {
  request_id: string
  request_type: ApprovalType
  requester_user_id: string
  approver_user_id?: string | null
  target_id?: string | null
  payload: Record<string, unknown>
  status: ApprovalStatus
  reason: string
  decision_comment?: string | null
  supplement?: string | null
  created_at: string
  decided_at?: string | null
  result?: { key_id: string; api_key: string }
}

export interface ApprovalFilters {
  request_type?: ApprovalType
  status?: ApprovalStatus
  requester_user_id?: string
  project_id?: string
}

export interface ProjectAccessOption {
  project_id: string
  name: string
  department_name: string
  owner_user_id?: string | null
}

export interface ModelGroupApplicationOption {
  group_id: string
  name: string
}

export const getMyApprovals = () => get<ApprovalRequest[]>('/approvals/mine')

export const getAssignedApprovals = (filters?: ApprovalFilters) =>
  get<ApprovalRequest[]>('/approvals/review', { params: filters })

export const getApprovalRequesters = () =>
  get<{ user_id: string; username: string }[]>('/approvals/review/requesters')

export const getProjectAccessOptions = () =>
  get<ProjectAccessOption[]>('/approvals/project-access/options')

export const getModelGroupApplicationOptions = () =>
  get<ModelGroupApplicationOption[]>('/approvals/model-group/options')

export const createApiKeyApplication = (data: {
  project_id: string
  name: string
  ip_whitelist: string[]
  expires_at: string | null
  reason: string
}) => post<ApprovalRequest>('/approvals/api-key', data)

export const createQuotaApplication = (data: { amount: number; reason: string }) =>
  post<ApprovalRequest>('/approvals/quota', data)

export const createModelGroupApplication = (data: { group_id: string; reason: string }) =>
  post<ApprovalRequest>('/approvals/model-group', data)

export const createProjectAccessApplication = (data: { project_id: string; reason: string }) =>
  post<ApprovalRequest>('/approvals/project-access', data)

export const cancelApproval = (requestId: string) =>
  post<ApprovalRequest>(`/approvals/${requestId}/cancel`)

export const supplementApproval = (requestId: string, content: string) =>
  post<ApprovalRequest>(`/approvals/${requestId}/supplement`, { content })

export const decideApproval = (requestId: string, decision: 'approved' | 'rejected' | 'needs_info', comment: string) =>
  post<ApprovalRequest>(`/approvals/${requestId}/decision`, { decision, comment })
