import { useEffect, useState } from 'react'
import useLeaderboardStore from '../stores/leaderboardStore'
import useAuthStore from '../stores/authStore'
import LeaderboardRow from '../components/LeaderboardRow'

export default function Leaderboard() {
  const { rankings, teamStats, weeklyRankings, loading, fetchLeaderboard, fetchTeamStats, fetchWeekly } = useLeaderboardStore()
  const user = useAuthStore((s) => s.user)
  const [teamFilter, setTeamFilter] = useState('')

  useEffect(() => { fetchLeaderboard(teamFilter) }, [teamFilter])
  useEffect(() => { fetchTeamStats(); fetchWeekly() }, [])

  const tabs = [
    { value: '', label: 'ALL' },
    { value: 'red', label: 'RED' },
    { value: 'blue', label: 'BLUE' },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Rankings</h1>
        <div className="flex rounded-lg overflow-hidden ml-4" style={{ border: '1px solid var(--border)' }}>
          {tabs.map((t) => (
            <button key={t.value} onClick={() => setTeamFilter(t.value)}
              className="px-4 py-1.5 text-xs font-mono font-bold"
              style={{
                background: teamFilter === t.value ? 'rgba(0,200,255,0.1)' : 'var(--bg-surface)',
                color: teamFilter === t.value ? 'var(--accent-cyan)' : 'var(--text-muted)',
              }}>
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-lg overflow-hidden" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
        <div className="grid grid-cols-[3rem_1fr_6rem_4rem_4rem] gap-2 px-4 py-2 text-[10px] font-mono tracking-wider" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
          <span>RANK</span><span>OPERATOR</span><span>POINTS</span><span>FLAGS</span><span>STREAK</span>
        </div>
        {loading ? (
          <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>Loading...</div>
        ) : rankings.length === 0 ? (
          <div className="p-8 text-center text-sm" style={{ color: 'var(--text-muted)' }}>No rankings yet</div>
        ) : (
          rankings.map((m, i) => (
            <div key={m.user_id || i} style={{
              background: m.user_id === user?.id ? 'rgba(0,200,255,0.05)' : 'transparent',
            }}>
              <LeaderboardRow member={m} index={i} />
            </div>
          ))
        )}
      </div>

      {teamStats && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {(Array.isArray(teamStats) ? teamStats : [teamStats.red, teamStats.blue].filter(Boolean)).map((ts) => (
            <div key={ts?.team} className="rounded-lg p-4" style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderLeft: `3px solid ${ts?.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)'}`,
            }}>
              <h3 className="text-sm font-bold mb-3" style={{ color: ts?.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)' }}>
                {ts?.team?.toUpperCase()} TEAM
              </h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span style={{ color: 'var(--text-muted)' }}>Points:</span> <strong style={{ color: 'var(--text-primary)' }}>{ts?.total_points || 0}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>Flags:</span> <strong style={{ color: 'var(--text-primary)' }}>{ts?.total_solves || 0}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>Members:</span> <strong style={{ color: 'var(--text-primary)' }}>{ts?.member_count || 0}</strong></div>
                <div><span style={{ color: 'var(--text-muted)' }}>Avg:</span> <strong style={{ color: 'var(--text-primary)' }}>{Math.round(ts?.avg_points_per_member || 0)}</strong></div>
              </div>
            </div>
          ))}
        </div>
      )}

      {weeklyRankings.length > 0 && (
        <div>
          <h2 className="text-lg font-bold mb-3" style={{ color: 'var(--text-primary)' }}>This Week</h2>
          <div className="rounded-lg overflow-hidden" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            {weeklyRankings.slice(0, 10).map((m, i) => <LeaderboardRow key={m.user_id || i} member={m} index={i} />)}
          </div>
        </div>
      )}
    </div>
  )
}
