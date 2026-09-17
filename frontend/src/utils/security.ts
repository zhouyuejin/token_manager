import type { ApiKey } from '../api/apiKeys'

export const getApiKeyStatus = (key: Pick<ApiKey, 'status' | 'expires_at' | 'revoked_at' | 'frozen_at'>, now = Date.now()) => {
  if (key.revoked_at || key.status === 'revoked') return 'revoked'
  if (key.frozen_at) return 'frozen'
  if (key.expires_at && Date.parse(key.expires_at) <= now) return 'expired'
  return key.status
}

export const maskKey = (key?: string | null) => {
  if (!key) return '***'
  if (key.includes('...') || key.includes('*')) return key
  if (key.length < 14) return '***'
  return `${key.slice(0, 6)}...${key.slice(-4)}`
}

export const getRequestErrorMessage = (data: any, fallback: string): string => {
  if (typeof data === 'string') return data || fallback
  if (typeof data?.detail === 'string') return data.detail || fallback
  if (Array.isArray(data?.detail)) {
    return data.detail.map((e: any) => `${(e?.loc || []).join('.')}: ${e?.msg || ''}`).join('; ') || fallback
  }
  if (data?.error) return getRequestErrorMessage(data.error, fallback)
  return typeof data?.message === 'string' && data.message ? data.message : fallback
}
