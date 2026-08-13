import { create } from 'zustand'
import client from '../api/client'
import { reportIgnored } from '../lib/report'

const useNotificationStore = create((set) => ({
  notifications: [],
  unreadCount: 0,

  fetchNotifications: async () => {
    try {
      const res = await client.get('/notifications')
      set({ notifications: res.data.items || res.data })
    } catch (err) { reportIgnored('notifications.fetch', err) }
  },

  markRead: async (id) => {
    try {
      await client.put(`/notifications/${id}/read`)
      set((s) => ({
        notifications: s.notifications.map((n) => n.id === id ? { ...n, is_read: true } : n),
        unreadCount: Math.max(0, s.unreadCount - 1),
      }))
    } catch (err) { reportIgnored('notifications.markRead', err) }
  },

  markAllRead: async () => {
    try {
      await client.put('/notifications/read-all')
      set((s) => ({
        notifications: s.notifications.map((n) => ({ ...n, is_read: true })),
        unreadCount: 0,
      }))
    } catch (err) { reportIgnored('notifications.markAllRead', err) }
  },

  fetchUnreadCount: async () => {
    try {
      const res = await client.get('/notifications/unread-count')
      set({ unreadCount: res.data.count || 0 })
    } catch (err) { reportIgnored('notifications.unreadCount', err) }
  },

  addNotification: (notification) => {
    set((s) => ({
      notifications: [notification, ...s.notifications],
      unreadCount: s.unreadCount + 1,
    }))
  },
}))

export default useNotificationStore
