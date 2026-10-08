import { get } from './request'

export interface OperationLog {
  log_id: string
  operator_id: string
  operator_name: string
  action: string
  target_type: string
  target_id: string
  detail: any
  ip_address: string
  created_at: string
}

export interface LoginLog {
  log_id: string
  username: string
  user_id: string
  ip_address: string
  user_agent: string
  status: string
  failure_reason: string
  created_at: string
}

export interface OperationLogListResponse {
  total: number
  items: OperationLog[]
}

export interface LoginLogListResponse {
  total: number
  items: LoginLog[]
}

export interface OperationLogParams {
  page: number
  page_size: number
  keyword?: string
  action?: string
  target_type?: string
  operator_id?: string
  start_date?: string
  end_date?: string
}

export interface LoginLogParams {
  page: number
  page_size: number
  keyword?: string
  status?: string
  start_date?: string
  end_date?: string
}

export interface RouteDecisionLog {
  id: number
  request_id: string
  user_id: string | null
  username?: string | null
  key_id: string | null
  model: string
  candidate_channels: string[]
  skipped_reasons: Record<string, string>
  selected_channel: string | null
  retry_path: { channel_id: string; status_code: number }[]
  status_code: number
  success: boolean
  error_message: string | null
  created_at: string
}

export interface RouteDecisionLogParams {
  page: number
  page_size: number
  request_id?: string
  user_id?: string
  key_id?: string
  model?: string
  channel_id?: string
  status_code?: number
}

export interface RouteDecisionLogListResponse {
  total: number
  items: RouteDecisionLog[]
}

export const getOperationLogs = (params: OperationLogParams) =>
  get<OperationLogListResponse>('/admin/logs/operations', { params })

export const getLoginLogs = (params: LoginLogParams) =>
  get<LoginLogListResponse>('/admin/logs/logins', { params })

export const getRouteDecisionLogs = (params: RouteDecisionLogParams) =>
  get<RouteDecisionLogListResponse>('/admin/logs/routes', { params })
