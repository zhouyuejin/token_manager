import { create } from 'zustand'

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

interface NotificationState {
  unreadCount: number
  notifications: Notification[]
  setUnreadCount: (count: number | ((prev: number) => number)) => void
  addNotification: (notif: Notification) => void
  markAsRead: (notifId: string) => void
  markAllAsRead: () => void
  removeNotification: (notifId: string) => void
  replaceNotifications: (items: Notification[], unreadCount: number) => void
  clearRead: () => void
}

export const useNotificationStore = create<NotificationState>((set) => ({
  unreadCount: 0,
  notifications: [],
  
  setUnreadCount: (countOrFn) => set((state) => ({
    unreadCount: typeof countOrFn === 'function' 
      ? countOrFn(state.unreadCount) 
      : countOrFn
  })),
  
  addNotification: (notif) =>
    set((state) => ({
      notifications: [notif, ...state.notifications].slice(0, 50),
    })),
  
  markAsRead: (notifId) =>
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.notif_id === notifId ? { ...n, is_read: true } : n
      ),
      unreadCount: Math.max(0, state.unreadCount - 1),
    })),
  
  markAllAsRead: () =>
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, is_read: true })),
      unreadCount: 0,
    })),
  
  removeNotification: (notifId) =>
    set((state) => {
      const notif = state.notifications.find((n) => n.notif_id === notifId)
      return {
        notifications: state.notifications.filter((n) => n.notif_id !== notifId),
        unreadCount:
          notif && !notif.is_read ? Math.max(0, state.unreadCount - 1) : state.unreadCount,
      }
    }),

  replaceNotifications: (items, unreadCount) =>
    set({ notifications: items, unreadCount }),

  clearRead: () =>
    set((state) => ({
      notifications: state.notifications.filter((n) => !n.is_read),
    })),
}))
