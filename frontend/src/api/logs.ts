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

export const getOperationLogs = (params: OperationLogParams) =>
  get<OperationLogListResponse>('/admin/logs/operations', { params })

export const getLoginLogs = (params: LoginLogParams) =>
  get<LoginLogListResponse>('/admin/logs/logins', { params })
