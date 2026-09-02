import { get, put, del } from './request'

export interface Notification {
  notif_id: string
  type: string
  title: string
  content: string | null
  is_read: boolean
  metadata?: any
  created_at: string
  read_at: string | null
}

export const getNotifications = (params?: {
  page?: number
  page_size?: number
  type?: string
}) =>
  get<{
    total: number
    unread_count: number
    items: Notification[]
  }>('/notifications', { params })

export const getUnreadCount = () => get<{ unread_count: number }>('/notifications/unread-count')

export const markAsRead = (notifId: string) => put(`/notifications/${notifId}/read`)

export const markAllAsRead = () => put('/notifications/read-all')

export const deleteNotification = (notifId: string) => del(`/notifications/${notifId}`)

export const deleteReadNotifications = () =>
  del<{ message: string; deleted: number }>('/notifications')
