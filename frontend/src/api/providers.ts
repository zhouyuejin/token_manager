import { get, post, put, del } from './request'

export interface Provider {
  provider_id: string
  name: string
  type: string
  endpoint: string
  api_key: string
  priority: number
  timeout: number
  status: string
  health_status: string
  last_check_at: string
  quota_type: string
  quota_hourly: number
  quota_weekly: number
  models: string[]
}

export interface ProviderQuota {
  provider_id: string
  provider_name: string
  hourly: {
    limit: number
    used: number
    remain: number
    percent: number
    reset_at: string
    last_sync: string
    raw_data: any
  }
  weekly: {
    limit: number
    used: number
    remain: number
    percent: number
    reset_at: string
    last_sync: string
    raw_data: any
  }
}

export const getProviders = () => get<{ items: Provider[] }>('/admin/providers')

export const createProvider = (data: Omit<Provider, 'provider_id' | 'health_status' | 'last_check_at'>) =>
  post('/admin/providers', data)

export const updateProvider = (providerId: string, data: Partial<Provider>) =>
  put(`/admin/providers/${providerId}`, data)

export const deleteProvider = (providerId: string) =>
  del(`/admin/providers/${providerId}`)

export const getProviderQuota = (providerId: string) =>
  get<ProviderQuota>(`/admin/providers/${providerId}/quota`)

export const getAllProviderQuotas = () =>
  get<{ items: any[] }>('/admin/providers/quotas')

export const syncProviderQuota = (providerId: string) =>
  post(`/admin/providers/${providerId}/quota/sync`)

export const updateProviderQuota = (providerId: string, data: {
  quota_hourly?: number
  quota_weekly?: number
  sync_enabled?: boolean
  sync_interval?: number
}) => put(`/admin/providers/${providerId}/quota`, data)
