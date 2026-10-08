import { get, post, put, del } from './request'
import { hashPassword } from '../utils/crypto'

export interface User {
  user_id: string
  username: string
  nickname?: string | null
  email: string
  role: string
  status: string
  quota: number
  quota_used: number
  unlimited: boolean
  created_at: string
  model_group_ids: string[]
  qps_limit: number
  rpm_limit: number
  tpm_limit: number
  concurrency_limit: number
}

export interface CreateUserParams {
  username: string
  nickname?: string | null
  email: string
  password: string
  role?: string
  quota?: number
  model_group_ids?: string[]
  qps_limit?: number
  rpm_limit?: number
  tpm_limit?: number
  concurrency_limit?: number
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
  nickname?: string | null
  username?: string
  email?: string
  quota?: number
  status?: string
  role?: string
  model_group_ids?: string[]
  qps_limit?: number
  rpm_limit?: number
  tpm_limit?: number
  concurrency_limit?: number
}) => put(`/admin/users/${userId}`, data)

export const deleteUser = (userId: string) => del(`/admin/users/${userId}`)

export interface QuotaAdjustParams {
  amount?: number
  set_unlimited?: boolean
  reason: string
}

export const adjustQuota = (userId: string, data: QuotaAdjustParams) => post(`/admin/users/${userId}/quota`, data)

export async function changePassword(data: { old_password: string; new_password: string }): Promise<void> {
  await put('/users/me/password', {
    old_password: await hashPassword(data.old_password),
    new_password: await hashPassword(data.new_password),
  })
}

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

export const updateProfile = (data: { nickname: string | null }) =>
  put('/users/me/profile', data)

export const uploadAvatar = (file: File) => {
  const data = new FormData()
  data.append('file', file)
  return put('/users/me/avatar', data)
}

export const removeAvatar = () => del('/users/me/avatar')
