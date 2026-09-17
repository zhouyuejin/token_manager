import { get, post, put, del } from './request'

export interface ApiKey {
  key_id: string
  project_id?: string | null
  project_name?: string | null
  department_id?: string | null
  department_name?: string | null
  user_id: string
  api_key: string
  name: string
  ip_whitelist: string[]
  status: string
  created_at: string
  last_used_at: string | null
  expires_at?: string | null
  revoked_at?: string | null
  frozen_at?: string | null
  frozen_reason?: string | null
  revoked_reason?: string | null
  last_used_ip?: string | null
  last_used_user_agent?: string | null
  qps_limit: number
  rpm_limit: number
  tpm_limit: number
  concurrency_limit: number
}

export interface CreateApiKeyParams {
  project_id: string
  name: string
  ip_whitelist?: string[]
  expires_at?: string | null
  qps_limit?: number
  rpm_limit?: number
  tpm_limit?: number
  concurrency_limit?: number
}

export const getApiKeys = () => get<{ items: ApiKey[] }>('/api-keys')

export const getAllApiKeys = () => get<{ items: ApiKey[] }>('/api-keys/admin')

export const createApiKey = (data: CreateApiKeyParams) => 
  post<{ api_key: string; name: string; key_id: string }>('/api-keys', data)

export const updateApiKey = (keyId: string, data: Partial<CreateApiKeyParams>) =>
  put(`/api-keys/${keyId}`, data)

export const deleteApiKey = (keyId: string) => del(`/api-keys/${keyId}`)

export const updateApiKeyStatus = (keyId: string, status: string) =>
  put(`/api-keys/${keyId}/status`, { status })

export const revokeApiKey = (keyId: string, reason?: string) =>
  put(`/api-keys/${keyId}/revoke`, { reason })

export const rotateApiKey = (keyId: string) =>
  post<{ api_key: string; name: string; key_id: string; expires_at?: string | null }>(`/api-keys/${keyId}/rotate`, {})

export const unfreezeApiKey = (keyId: string) =>
  put(`/api-keys/admin/${keyId}/unfreeze`, {})

export const updateAdminApiKey = (keyId: string, data: Partial<CreateApiKeyParams>) =>
  put(`/api-keys/admin/${keyId}`, data)
