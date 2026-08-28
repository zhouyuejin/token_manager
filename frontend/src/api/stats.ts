import { get } from './request'

export interface UsageStats {
  total_tokens: number
  total_requests: number
  avg_latency_ms: number
  success_rate: number
  by_model: {
    model: string
    tokens: number
    requests: number
    cost: number
  }[]
  by_day: {
    date: string
    tokens: number
    requests: number
  }[]
}

export const getUsageStats = (params: {
  start_date: string
  end_date: string
  group_by?: string
}) => get<UsageStats>('/stats/usage', { params })

export interface AdminStats {
  total_tokens: number
  total_requests: number
  by_user: {
    user_id: string
    username: string
    tokens: number
  }[]
  by_provider: {
    provider: string
    tokens: number
  }[]
}

export const getAdminStats = (params: {
  start_date: string
  end_date: string
  group_by?: string
}) => get<AdminStats>('/admin/stats/usage', { params })
