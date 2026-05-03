import { useState, useEffect, useRef } from 'react'
import { ChevronDown, ChevronUp, Zap } from 'lucide-react'
import useWebSocket from '../hooks/useWebSocket'

export default function LiveFeed() {
  const [collapsed, setCollapsed] = useState(false)
  const [events, setEvents] = useState([])
  const scrollRef = useRef(null)
  const { lastMessage } = useWebSocket()

  useEffect(() => {
    if (lastMessage && lastMessage.type === 'flag_captured') {
      setEvents((prev) => [
        { ...lastMessage, time: new Date().toLocaleTimeString() },
        ...prev,
      ].slice(0, 20))
    }
  }, [lastMessage])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0
  }, [events])

  return (
    <div className="fixed bottom-4 right-4 z-40 w-72" style={{ fontFamily: 'JetBrains Mono, monospace' }}>
      <div className="rounded-lg overflow-hidden shadow-xl" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-between px-3 py-2 text-xs font-bold"
          style={{ color: 'var(--accent-cyan)', background: 'var(--bg-surface)' }}
        >
          <span className="flex items-center gap-1"><Zap size={12} /> LIVE FEED</span>
          {collapsed ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
        {!collapsed && (
          <div ref={scrollRef} className="max-h-48 overflow-y-auto p-2 space-y-1">
            {events.length === 0 ? (
              <div className="text-[11px] py-4 text-center" style={{ color: 'var(--text-muted)' }}>Waiting for captures...</div>
            ) : (
              events.map((e, i) => (
                <div key={i} className="text-[11px] py-1 px-2 rounded" style={{ color: 'var(--text-secondary)', background: 'var(--bg-primary)' }}>
                  <span style={{ color: 'var(--accent-green)' }}>{e.user || e.username}</span>
                  {' captured '}
                  <span style={{ color: 'var(--accent-cyan)' }}>{e.challenge || e.challenge_title}</span>
                  {' '}
                  <span style={{ color: 'var(--accent-yellow)' }}>({e.points}pts)</span>
                  <span className="float-right" style={{ color: 'var(--text-muted)' }}>{e.time}</span>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
