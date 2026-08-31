import { get, post, put, del } from './request'

export interface ModelMapping {
  model_id: string
  display_name: string
  description?: string
  provider_id: string
  provider_model: string
  aliases: string[] | string
  // 定价配置
  price_type: string  // token 或 request
  price_per_1k_input: number
  price_per_1k_output: number
  price_per_request: number
  status: string
  created_at?: string
}

export const getModels = () => get<{ items: ModelMapping[] }>('/admin/models')

export const createModel = (data: Omit<ModelMapping, 'model_id' | 'created_at'>) =>
  post('/admin/models', data)

export const updateModel = (modelId: string, data: Partial<ModelMapping>) =>
  put(`/admin/models/${modelId}`, data)

export const deleteModel = (modelId: string) => del(`/admin/models/${modelId}`)
