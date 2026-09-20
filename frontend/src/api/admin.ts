import { get } from './request'

export interface UsageReportParams {
  start_date: string
  end_date: string
  department_id?: string
  project_id?: string
  user_id?: string
  model?: string
  channel_id?: string
}

export interface AdminUserUsage {
  user_id: string
  username: string
  tokens: number
  requests: number
}

export interface AdminProviderUsage {
  provider: string
  tokens: number
  requests: number
}

export interface AdminModelUsage {
  model: string
  display_name?: string
  tokens: number
  requests: number
  cost: number
}

export interface AdminDailyUsage {
  date: string
  tokens: number
  requests: number
}

export interface AdminStats {
  total_tokens: number
  total_requests: number
  total_cost: number
  avg_latency_ms: number
  success_rate: number
  by_user: AdminUserUsage[]
  by_provider: AdminProviderUsage[]
  by_model: AdminModelUsage[]
  by_day: AdminDailyUsage[]
}

export const getAdminStats = (params: UsageReportParams) =>
  get<AdminStats>('/admin/stats/usage', { params })

export const exportUsageReport = (params: UsageReportParams) =>
  get<Blob>('/admin/stats/usage/export', { params, responseType: 'blob', timeout: 120000 })

// 系统概览数据
export interface SystemOverview {
  total_users: number
  active_users: number
  total_api_keys: number
  active_api_keys: number
  total_providers: number
  active_providers: number
  total_model_mappings: number
}

export const getSystemOverview = () => get<SystemOverview>('/admin/stats/overview')
