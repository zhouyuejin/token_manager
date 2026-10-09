import { get, put } from './request'

export interface AlertRuleConfig {
  channel_error_rate_percent: number
  channel_error_min_requests: number
  quota_remaining_percent: number
  project_growth_multiplier: number
  project_growth_min_cost_cny: number
}

export const getAlertRules = () => get<AlertRuleConfig>('/admin/alerts/rules')
export const updateAlertRules = (data: AlertRuleConfig) => put<AlertRuleConfig>('/admin/alerts/rules', data)
