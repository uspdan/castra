import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Target, Flag, TrendingUp, Flame, ArrowRight } from 'lucide-react'
import client from '../api/client'
import WeeklyActivity from '../components/WeeklyActivity'
import LeaderboardRow from '../components/LeaderboardRow'
import MitreCoverage from '../components/MitreCoverage'

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [activity, setActivity] = useState([])
  const [leaders, setLeaders] = useState([])
  const [mitre, setMitre] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      client.get('/stats/overview').catch(() => ({ data: {} })),
      client.get('/stats/activity').catch(() => ({ data: [] })),
      // Phase 12 (slice 21): v1 scoreboard uses `limit` (not
      // `per_page`) and returns {entries, team_filter, generated_at}.
      client.get('/api/v1/scoreboard', { params: { limit: 5 } }).catch(() => ({ data: { entries: [] } })),
      client.get('/stats/mitre').catch(() => ({ data: [] })),
    ]).then(([s, a, l, m]) => {
      setStats(s.data)
      setActivity(Array.isArray(a.data) ? a.data.slice(-7) : [])
      const leaderRows = Array.isArray(l.data?.entries)
        ? l.data.entries
        : Array.isArray(l.data) ? l.data : []
      setLeaders(leaderRows.slice(0, 5))
      setMitre(Array.isArray(m.data) ? m.data : [])
      setLoading(false)
    })
  }, [])

  const cards = stats ? [
    { label: 'TOTAL CHALLENGES', value: stats.total_challenges || 0, sub: `${stats.red_count || '—'} ATK / ${stats.blue_count || '—'} DEF`, color: 'var(--accent-cyan)', icon: Target },
    { label: 'TEAM SOLVES', value: stats.total_solves || 0, sub: `across ${stats.active_users || 0} operators`, color: 'var(--accent-green)', icon: Flag },
    { label: 'AVG COMPLETION', value: `${Math.round((stats.avg_completion || 0) * 100)}%`, sub: 'per operator', color: 'var(--accent-yellow)', icon: TrendingUp },
    { label: 'ACTIVE STREAKS', value: stats.active_streaks || 0, sub: `of ${stats.total_users || 0} operators`, color: 'var(--accent-red)', icon: Flame },
  ] : []

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1,2,3,4].map((i) => (
            <div key={i} className="h-24 rounded-lg animate-pulse" style={{ background: 'var(--bg-surface)' }} />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="h-64 rounded-lg animate-pulse" style={{ background: 'var(--bg-surface)' }} />
          <div className="h-64 rounded-lg animate-pulse" style={{ background: 'var(--bg-surface)' }} />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {cards.map((card) => (
          <div key={card.label} className="rounded-lg p-4 animate-float-up" style={{
            background: 'var(--bg-surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${card.color}`,
          }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono tracking-wider" style={{ color: 'var(--text-muted)' }}>{card.label}</span>
              <card.icon size={16} style={{ color: card.color }} />
            </div>
            <div className="text-2xl font-bold" style={{ fontFamily: 'Outfit', color: 'var(--text-primary)' }}>{card.value}</div>
            <div className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>{card.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <WeeklyActivity data={activity} />
        <div className="rounded-lg p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold font-mono" style={{ color: 'var(--text-secondary)' }}>TOP OPERATORS</h3>
            <Link to="/leaderboard" className="text-xs font-mono flex items-center gap-1" style={{ color: 'var(--accent-cyan)' }}>
              VIEW ALL <ArrowRight size={12} />
            </Link>
          </div>
          {leaders.map((m, i) => <LeaderboardRow key={m.user_id || i} member={m} index={i} />)}
        </div>
      </div>

      <MitreCoverage data={mitre} />
    </div>
  )
}
