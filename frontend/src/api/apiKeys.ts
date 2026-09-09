import { get, post, put, del } from './request'

export interface ApiKey {
  key_id: string
  api_key: string
  name: string
  ip_whitelist: string[]
  status: string
  created_at: string
  last_used_at: string | null
}

export interface CreateApiKeyParams {
  name: string
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
