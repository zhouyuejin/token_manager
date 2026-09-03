import { get, post, put, del } from './request'

export interface ApiKey {
  key_id: string
  api_key: string
  name: string
  daily_limit: number
  daily_used: number
  monthly_limit: number
  monthly_used: number
  qps_limit: number
  ip_whitelist: string[]
  status: string
  created_at: string
  last_used_at: string | null
}

export interface CreateApiKeyParams {
  name: string
  daily_limit?: number
  monthly_limit?: number
  qps_limit?: number
  ip_whitelist?: string[]
}

export const getApiKeys = () => get<{ items: ApiKey[] }>('/api-keys')

export const getAllApiKeys = () => get<{ items: ApiKey[] }>('/api-keys/admin/all')

export const createApiKey = (data: CreateApiKeyParams) => 
  post<{ api_key: string; name: string; key_id: string }>('/api-keys', data)

export const updateApiKey = (keyId: string, data: Partial<CreateApiKeyParams>) =>
  put(`/api-keys/${keyId}`, data)

export const deleteApiKey = (keyId: string) => del(`/api-keys/${keyId}`)

export const updateApiKeyStatus = (keyId: string, status: string) =>
  put(`/api-keys/${keyId}/status`, { status })
