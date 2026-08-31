import { get, post, put, del } from './request'

export interface User {
  user_id: string
  username: string
  email: string
  role: string
  status: string
  quota: number
  quota_used: number
  created_at: string
  model_group_ids: string[]
}

export interface CreateUserParams {
  username: string
  email: string
  password: string
  role?: string
  quota?: number
  model_group_ids?: string[]
}

export const getUsers = (params?: {
  page?: number
  page_size?: number
  keyword?: string
  role?: string
  status?: string
}) => get<{ total: number; items: User[] }>('/admin/users', { params })

export const createUser = (data: CreateUserParams) => post('/admin/users', data)

export const updateUser = (userId: string, data: {
  quota?: number
  status?: string
  role?: string
  model_group_ids?: string[]
}) => put(`/admin/users/${userId}`, data)

export const deleteUser = (userId: string) => del(`/admin/users/${userId}`)

export const adjustQuota = (userId: string, data: {
  amount: number
  reason: string
}) => post(`/admin/users/${userId}/quota`, data)

export const resetPassword = (userId: string, newPassword: string) =>
  post(`/admin/users/${userId}/reset-password`, { new_password: newPassword })
