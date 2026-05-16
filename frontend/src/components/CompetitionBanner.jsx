import { useEffect, useState } from 'react'
import { Trophy } from 'lucide-react'
import { Link } from 'react-router-dom'
import client from '../api/client'

export default function CompetitionBanner() {
  const [comp, setComp] = useState(null)
  const [timeLeft, setTimeLeft] = useState('')

  useEffect(() => {
    client.get('/competitions/', { params: { active: true } }).then((res) => {
      const active = Array.isArray(res.data) ? res.data.find((c) => c.is_active) : null
      if (active) setComp(active)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (!comp) return
    const interval = setInterval(() => {
      const diff = new Date(comp.ends_at) - Date.now()
      if (diff <= 0) { setTimeLeft('ENDED'); clearInterval(interval); return }
      const d = Math.floor(diff / 86400000)
      const h = Math.floor((diff % 86400000) / 3600000)
      const m = Math.floor((diff % 3600000) / 60000)
      const s = Math.floor((diff % 60000) / 1000)
      setTimeLeft(`${d}d ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`)
    }, 1000)
    return () => clearInterval(interval)
  }, [comp])

  if (!comp) return null

  return (
    <div className="w-full py-2 px-4 flex items-center justify-center gap-4 text-sm" style={{
      background: 'linear-gradient(90deg, rgba(255,62,108,0.15), rgba(0,200,255,0.15))',
      borderBottom: '1px solid var(--border)',
    }}>
      <Trophy size={16} style={{ color: 'var(--accent-yellow)' }} />
      <span className="font-bold" style={{ color: 'var(--text-primary)' }}>{comp.title}</span>
      <span className="font-mono text-xs" style={{ color: 'var(--accent-cyan)' }}>{timeLeft}</span>
      <Link to={`/leaderboard`} className="text-xs font-mono underline" style={{ color: 'var(--accent-cyan)' }}>View Scoreboard</Link>
    </div>
  )
}
