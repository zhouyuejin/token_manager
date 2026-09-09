import { get, post, put, del } from './request'

export interface Model {
  model_id: string
  display_name?: string
  description?: string
  aliases?: string[]
  price_type: 'token' | 'request'
  price_per_1k_input: number
  price_per_1k_output: number
  price_per_request: number
  status: string
  created_at?: string
  bound_channels_count?: number
  model_groups?: string[]
}

export interface ModelChannel {
  id: number
  model_id: string
  channel_id: string
  upstream_model: string
  priority: number
  weight: number
  enabled: boolean
  created_at?: string
  channel?: any
}

export const getModels = () => get<{ total: number; items: Model[] }>('/admin/models')

export const createModel = (data: Partial<Model>) =>
  post<Model>('/admin/models', data)

export const updateModel = (modelId: string, data: Partial<Model>) =>
  put(`/admin/models/${modelId}`, data)

export const deleteModel = (modelId: string) =>
  del(`/admin/models/${modelId}`)

export const getModel = (modelId: string) =>
  get<Model & { bound_channels: ModelChannel[] }>(`/admin/models/${modelId}`)

// Model-Channel bindings
export const getModelChannels = (modelId: string) =>
  get<ModelChannel[]>(`/admin/models/${modelId}/channels`)

export const bindChannelToModel = (modelId: string, data: {
  channel_id: string
  upstream_model: string
  priority?: number
  weight?: number
  enabled?: boolean
}) => post<{ id: number }>(`/admin/models/${modelId}/channels`, data)

export const replaceModelChannels = (modelId: string, data: any[]) =>
  put(`/admin/models/${modelId}/channels`, data)

export const unbindChannel = (modelId: string, channelId: string) =>
  del(`/admin/models/${modelId}/channels/${channelId}`)

export const updateModelChannel = (modelId: string, channelId: string, data: Partial<ModelChannel>) =>
  patch(`/admin/models/${modelId}/channels/${channelId}`, data)

function patch(url: string, data: any) {
  return put(url, data) // FastAPI 的 PATCH 等同于 PUT
}
