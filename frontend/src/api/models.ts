import { get, post, put, del } from './request'

export interface ModelMapping {
  model_id: string
  display_name: string
  provider_id: string
  provider_model: string
  aliases: string[]
  status: string
}

export const getModels = () => get<{ items: ModelMapping[] }>('/admin/models')

export const createModel = (data: Omit<ModelMapping, 'model_id'>) =>
  post('/admin/models', data)

export const updateModel = (modelId: string, data: Partial<ModelMapping>) =>
  put(`/admin/models/${modelId}`, data)

export const deleteModel = (modelId: string) => del(`/admin/models/${modelId}`)
