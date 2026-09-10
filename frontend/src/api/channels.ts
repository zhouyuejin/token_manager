import { get, post, put, del } from './request'

export interface Channel {
  channel_id: string
  name: string
  type: string
  endpoint: string
  api_key: string
  extra_keys?: string[]
  key_strategy?: 'round_robin' | 'random' | 'sequential'
  priority: number
  timeout: number
  status: string
  health_status: string
  last_check_at?: string
  cooldown_until?: string
  quota_type: string
  quota_hourly: number
  quota_weekly: number
  sync_enabled: boolean
  sync_interval: number
  last_sync_at?: string
  quota_config?: {
    model_name?: string
    custom_api_path?: string
    extra_params?: Record<string, string>
  }
  bound_models_count?: number
}

export interface ChannelQuota {
  channel_id: string
  channel_name?: string
  hourly?: QuotaDetail
  weekly?: QuotaDetail
}

interface QuotaDetail {
  limit: number
  used: number
  remain: number
  percent: number
  last_sync?: string
  raw_data?: any
}

export const getChannels = () => get<{ total: number; items: Channel[] }>('/admin/channels')

export const createChannel = (data: Partial<Channel>) =>
  post<Channel>('/admin/channels', data)

export const updateChannel = (channelId: string, data: Partial<Channel>) =>
  put(`/admin/channels/${channelId}`, data)

export const deleteChannel = (channelId: string) =>
  del(`/admin/channels/${channelId}`)

export const getChannel = (channelId: string) =>
  get<Channel & { bound_models: any[] }>(`/admin/channels/${channelId}`)

export const getChannelQuota = (channelId: string) =>
  get<ChannelQuota>(`/admin/channels/${channelId}/quota`)

export const getAllChannelQuotas = () =>
  get<{ total: number; items: ChannelQuota[] }>('/admin/channels/quotas')

export const syncChannelQuota = (channelId: string) =>
  post(`/admin/channels/${channelId}/quota/sync`)

export const updateChannelQuota = (channelId: string, data: {
  quota_hourly?: number
  quota_weekly?: number
  sync_enabled?: boolean
  sync_interval?: number
  quota_config?: Channel['quota_config']
}) => put(`/admin/channels/${channelId}/quota`, data)

export const getChannelModels = (channelId: string) =>
  get<{ channel_id: string; channel_name: string; total: number; items: any[] }>(
    `/admin/channels/${channelId}/models`
  )

export const syncChannelModels = (channelId: string) =>
  post<{ success: boolean; count: number; models: any[]; message: string }>(
    `/admin/channels/${channelId}/sync-models`
  )

export const testChannelConnection = (data: {
  type: string
  endpoint: string
  api_key: string
  timeout?: number
}) => post<{
  success: boolean
  status_code?: number | null
  latency_ms: number
  message: string
  url?: string | null
}>('/admin/channels/test-connection', data)
