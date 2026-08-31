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
  // 同步配置
  sync_enabled: boolean
  sync_interval: number  // 单位：秒
  last_sync_at: string
  // 自定义用量查询配置（不同供应商查询方式不同）
  quota_config?: {
    // 查询的模型名称（某些供应商需要指定模型查询用量）
    model_name?: string
    // 自定义API路径（某些供应商需要不同的API端点）
    custom_api_path?: string
    // 其他自定义参数
    extra_params?: Record<string, string>
  }
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

export const createProvider = (data: Omit<Provider, 'provider_id' | 'health_status' | 'last_check_at' | 'last_sync_at'>) =>
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
  quota_config?: Provider['quota_config']
}) => put(`/admin/providers/${providerId}/quota`, data)

// 模型同步
export const getProviderModels = (providerId: string) =>
  get<{ provider_id: string; provider_name: string; models: any[]; last_sync_at: string }>(
    `/admin/providers/${providerId}/models`
  )

export const syncProviderModels = (providerId: string) =>
  post<{ success: boolean; count: number; models: any[]; message: string }>(
    `/admin/providers/${providerId}/models/sync`
  )

export const syncAllProviderModels = () =>
  post<{ total: number; success: number; failed: number; results: any[] }>(
    '/admin/providers/models/sync-all'
  )

// 自动创建模型映射
export const autoCreateModelMappings = (providerId: string) =>
  post<{ 
    sync_success: boolean; 
    sync_count: number; 
    mapping_created: number; 
    mapping_skipped: number; 
    message: string 
  }>(`/admin/providers/${providerId}/models/auto-create-mappings`)

export const syncAllWithMappings = () =>
  post<{ 
    total_providers: number; 
    total_models: number; 
    total_mappings: number; 
    results: any[] 
  }>('/admin/providers/models/sync-all-with-mappings')
