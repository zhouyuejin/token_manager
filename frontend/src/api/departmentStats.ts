import { get } from './request'

export interface DepartmentUsageStatsParams {
  start_date: string
  end_date: string
  department_id?: string
}

export interface DepartmentDailyUsage {
  date: string
  tokens: number
  requests: number
}

export interface DepartmentProjectUsage {
  project_id: string
  name: string
  tokens: number
  requests: number
}

export interface DepartmentUsageStats {
  total_tokens: number
  total_requests: number
  total_cost: number
  success_rate: number
  by_day: DepartmentDailyUsage[]
  by_project: DepartmentProjectUsage[]
  web_chat: { tokens: number; requests: number; cost: number }
}

export const getDepartmentUsageStats = (params: DepartmentUsageStatsParams) =>
  get<DepartmentUsageStats>('/projects/admin/usage-stats', { params })
