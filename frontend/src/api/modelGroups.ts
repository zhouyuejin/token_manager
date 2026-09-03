import { get, post, put, del } from './request'

export interface ModelGroup {
  group_id: string
  name: string
  description: string
  status: string
  is_default: number
  provider_ids: string[]
  created_at: string
}

export const getModelGroups = () => 
  get<{ items: ModelGroup[] }>('/admin/model-groups')

export const getModelGroup = (groupId: string) =>
  get<ModelGroup>(`/admin/model-groups/${groupId}`)

export const createModelGroup = (data: {
  name: string
  description?: string
  is_default?: number
  provider_ids?: string[]
}) => post<ModelGroup>('/admin/model-groups', data)

export const updateModelGroup = (groupId: string, data: Partial<ModelGroup>) =>
  put(`/admin/model-groups/${groupId}`, data)

export const deleteModelGroup = (groupId: string) =>
  del(`/admin/model-groups/${groupId}`)

export const setModelGroupDefault = (groupId: string) =>
  post(`/admin/model-groups/${groupId}/set-default`, {})

export const unsetModelGroupDefault = (groupId: string) =>
  post(`/admin/model-groups/${groupId}/unset-default`, {})
