import { useEffect, useState } from 'react'
import { Bell, Check } from 'lucide-react'
import useNotificationStore from '../stores/notificationStore'

export default function NotificationDropdown() {
  const { notifications, unreadCount, fetchNotifications, fetchUnreadCount, markRead, markAllRead } = useNotificationStore()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    fetchUnreadCount()
    fetchNotifications()
  }, [])

  const timeAgo = (dateStr) => {
    const diff = Date.now() - new Date(dateStr).getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'now'
    if (mins < 60) return `${mins}m`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h`
    return `${Math.floor(hrs / 24)}d`
  }

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="relative p-1.5 rounded hover:bg-white/5 transition-colors">
        <Bell size={18} style={{ color: 'var(--text-secondary)' }} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 rounded-full text-[10px] font-bold flex items-center justify-center" style={{ background: 'var(--accent-red)', color: 'white' }}>
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
            <span className="text-xs font-mono font-bold" style={{ color: 'var(--text-secondary)' }}>NOTIFICATIONS</span>
            {unreadCount > 0 && (
              <button onClick={() => markAllRead()} className="text-[11px] font-mono hover:underline" style={{ color: 'var(--accent-cyan)' }}>
                Mark all read
              </button>
            )}
          </div>
          {notifications.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>No notifications</div>
          ) : (
            notifications.slice(0, 20).map((n) => (
              <div
                key={n.id}
                onClick={() => !n.is_read && markRead(n.id)}
                className="px-4 py-3 cursor-pointer hover:bg-white/[0.03] flex items-start gap-3 border-b"
                style={{ borderColor: 'var(--border)', opacity: n.is_read ? 0.6 : 1 }}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate" style={{ color: 'var(--text-primary)' }}>{n.title}</div>
                  <div className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{n.message}</div>
                </div>
                <span className="text-[10px] font-mono shrink-0" style={{ color: 'var(--text-muted)' }}>{timeAgo(n.created_at)}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
