import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts'
import client from '../api/client'
import MitreCoverage from '../components/MitreCoverage'

export default function Profile() {
  const { username } = useParams()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    client.get(`/stats/user/${username}`).then((res) => {
      setProfile(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [username])

  if (loading) return <div className="animate-pulse h-96 rounded-lg" style={{ background: 'var(--bg-surface)' }} />
  if (!profile) return <div className="text-center py-20" style={{ color: 'var(--text-muted)' }}>User not found</div>

  const u = profile.user || profile
  const radarData = (profile.categories || []).map((c) => ({ category: c.name || c.category, value: c.percentage || c.count || 0 }))

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="rounded-lg p-6 flex items-center gap-6" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
        <div className="w-16 h-16 rounded-full flex items-center justify-center text-xl font-bold shrink-0" style={{
          background: 'var(--bg-elevated)',
          border: `3px solid ${u.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)'}`,
          color: 'var(--text-primary)',
        }}>
          {(u.display_name || u.username || '?')[0].toUpperCase()}
        </div>
        <div>
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>{u.display_name || u.username}</h1>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>@{u.username}</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded" style={{
              background: u.team === 'red' ? 'rgba(255,62,108,0.15)' : 'rgba(0,200,255,0.15)',
              color: u.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)',
            }}>{u.team === 'red' ? 'ATK' : 'DEF'}</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded" style={{ background: 'rgba(240,180,41,0.15)', color: 'var(--accent-yellow)' }}>{u.role}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Points', value: profile.total_points || u.total_points || 0, color: 'var(--accent-cyan)' },
          { label: 'Solves', value: profile.total_solves || u.total_solves || 0, color: 'var(--accent-green)' },
          { label: 'Streak', value: `${profile.current_streak || u.current_streak || 0}d`, color: 'var(--accent-yellow)' },
          { label: 'Rank', value: `#${profile.rank || u.rank || '-'}`, color: 'var(--accent-red)' },
        ].map((s) => (
          <div key={s.label} className="rounded-lg p-4 text-center" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
            <div className="text-2xl font-bold font-mono" style={{ color: s.color }}>{s.value}</div>
            <div className="text-[10px] font-mono tracking-wider mt-1" style={{ color: 'var(--text-muted)' }}>{s.label.toUpperCase()}</div>
          </div>
        ))}
      </div>

      {radarData.length > 0 && (
        <div className="rounded-lg p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
          <h3 className="text-sm font-bold font-mono mb-3" style={{ color: 'var(--text-secondary)' }}>SKILL RADAR</h3>
          <ResponsiveContainer width="100%" height={300}>
            <RadarChart data={radarData}>
              <PolarGrid stroke="#141C28" />
              <PolarAngleAxis dataKey="category" tick={{ fill: '#8899AA', fontSize: 11 }} />
              <Radar dataKey="value" stroke="#00C8FF" fill="#00C8FF" fillOpacity={0.2} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}

      {profile.mitre_coverage && <MitreCoverage data={profile.mitre_coverage} />}

      {profile.solves?.length > 0 && (
        <div className="rounded-lg p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
          <h3 className="text-sm font-bold font-mono mb-3" style={{ color: 'var(--text-secondary)' }}>SOLVE HISTORY</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>
                <th className="text-left pb-2">Challenge</th>
                <th className="text-left pb-2">Category</th>
                <th className="text-right pb-2">Points</th>
                <th className="text-right pb-2">Date</th>
              </tr>
            </thead>
            <tbody>
              {profile.solves.map((s, i) => (
                <tr key={i} style={{ borderTop: '1px solid var(--border)' }}>
                  <td className="py-2" style={{ color: 'var(--text-primary)' }}>{s.challenge_title || s.title}</td>
                  <td className="py-2" style={{ color: 'var(--text-muted)' }}>{s.category}</td>
                  <td className="py-2 text-right font-mono" style={{ color: 'var(--accent-cyan)' }}>{s.points_awarded || s.points}</td>
                  <td className="py-2 text-right font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{new Date(s.solved_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
