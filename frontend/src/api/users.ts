import { get, post, put, del } from './request'
import { hashPassword } from '../utils/crypto'

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

export interface NotificationSettings {
  quota_low_alert: boolean
  quota_change_alert: boolean
  daily_report: boolean
}

export const getUsers = (params?: {
  page?: number
  page_size?: number
  keyword?: string
  role?: string
  status?: string
}) => get<{ total: number; items: User[] }>('/admin/users', { params })

/**
 * 创建用户 - 密码在前端进行 SHA256 哈希后再传输
 */
export async function createUser(data: CreateUserParams): Promise<void> {
  const hashedPassword = await hashPassword(data.password)
  await post('/admin/users', {
    ...data,
    password: hashedPassword
  })
}

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

/**
 * 重置密码 - 密码在前端进行 SHA256 哈希后再传输
 */
export async function resetPassword(userId: string, newPassword: string): Promise<void> {
  const hashedPassword = await hashPassword(newPassword)
  await post(`/admin/users/${userId}/reset-password`, { new_password: hashedPassword })
}

// 通知设置相关API
export const getNotificationSettings = () => 
  get<NotificationSettings>('/users/me/notification-settings')

export const updateNotificationSettings = (settings: NotificationSettings) =>
  put<NotificationSettings>('/users/me/notification-settings', settings)
