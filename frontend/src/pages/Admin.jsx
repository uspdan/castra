import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, Trophy, FileText, Activity, Server } from 'lucide-react'
import useAuthStore from '../stores/authStore'
import client from '../api/client'

const tabs = [
  { id: 'users', label: 'Users', icon: Users },
  { id: 'challenges', label: 'Challenges', icon: Trophy },
  { id: 'competitions', label: 'Competitions', icon: Activity },
  { id: 'audit', label: 'Audit', icon: FileText },
  { id: 'system', label: 'System', icon: Server },
]

export default function Admin() {
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()
  const [tab, setTab] = useState('users')
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (user?.role !== 'admin') { navigate('/'); return }
    loadData()
  }, [tab])

  const loadData = async () => {
    setLoading(true)
    try {
      let res
      if (tab === 'users') res = await client.get('/admin/users')
      else if (tab === 'challenges') res = await client.get('/challenges', { params: { per_page: 100 } })
      else if (tab === 'competitions') res = await client.get('/competitions')
      else if (tab === 'audit') res = await client.get('/admin/audit')
      else if (tab === 'system') res = await client.get('/admin/system')
      setData(res?.data?.items || res?.data || [])
    } catch {} finally { setLoading(false) }
  }

  const tabStyle = { background: 'var(--bg-surface)', border: '1px solid var(--border)' }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Administration</h1>

      <div className="flex gap-1 rounded-lg p-1" style={{ background: 'var(--bg-surface)' }}>
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className="flex items-center gap-2 px-4 py-2 rounded text-sm font-medium transition-colors"
            style={{
              background: tab === t.id ? 'var(--bg-elevated)' : 'transparent',
              color: tab === t.id ? 'var(--accent-cyan)' : 'var(--text-muted)',
            }}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      <div className="rounded-lg p-4" style={tabStyle}>
        {loading ? (
          <div className="text-center py-8" style={{ color: 'var(--text-muted)' }}>Loading...</div>
        ) : tab === 'users' ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-mono" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                <th className="text-left pb-2">User</th><th className="text-left pb-2">Email</th>
                <th className="text-left pb-2">Role</th><th className="text-left pb-2">Team</th>
                <th className="text-right pb-2">Points</th><th className="text-center pb-2">Active</th>
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(data) ? data : []).map((u) => (
                <tr key={u.id} style={{ borderTop: '1px solid var(--border)' }}>
                  <td className="py-2" style={{ color: 'var(--text-primary)' }}>{u.display_name || u.username}</td>
                  <td className="py-2 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{u.email}</td>
                  <td className="py-2">
                    <button onClick={async () => {
                      const newRole = u.role === 'admin' ? 'operator' : 'admin'
                      await client.put(`/admin/users/${u.id}`, { role: newRole }); loadData()
                    }} className="text-xs font-mono px-2 py-0.5 rounded" style={{
                      background: u.role === 'admin' ? 'rgba(240,180,41,0.15)' : 'var(--bg-primary)',
                      color: u.role === 'admin' ? 'var(--accent-yellow)' : 'var(--text-muted)',
                    }}>{u.role}</button>
                  </td>
                  <td className="py-2 text-xs" style={{ color: u.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)' }}>{u.team || '-'}</td>
                  <td className="py-2 text-right font-mono" style={{ color: 'var(--accent-cyan)' }}>{u.total_points || 0}</td>
                  <td className="py-2 text-center">
                    <button onClick={async () => { await client.put(`/admin/users/${u.id}`, { is_active: !u.is_active }); loadData() }}
                      className="w-3 h-3 rounded-full" style={{ background: u.is_active ? 'var(--accent-green)' : 'var(--accent-red)' }} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : tab === 'challenges' ? (
          <div>
            <div className="flex justify-between mb-3">
              <span className="text-sm font-mono" style={{ color: 'var(--text-muted)' }}>{Array.isArray(data) ? data.length : 0} challenges</span>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-[10px] font-mono" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                  <th className="text-left pb-2">Title</th><th className="text-left pb-2">Category</th>
                  <th className="text-left pb-2">Team</th><th className="text-right pb-2">Points</th>
                  <th className="text-center pb-2">Released</th>
                </tr>
              </thead>
              <tbody>
                {(Array.isArray(data) ? data : []).map((c) => (
                  <tr key={c.id || c.slug} style={{ borderTop: '1px solid var(--border)' }}>
                    <td className="py-2" style={{ color: 'var(--text-primary)' }}>{c.title}</td>
                    <td className="py-2 text-xs" style={{ color: 'var(--text-muted)' }}>{c.category}</td>
                    <td className="py-2 text-xs" style={{ color: c.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)' }}>{c.team}</td>
                    <td className="py-2 text-right font-mono" style={{ color: 'var(--accent-yellow)' }}>{c.points}</td>
                    <td className="py-2 text-center">
                      {c.is_released ? (
                        <span className="text-xs" style={{ color: 'var(--accent-green)' }}>Live</span>
                      ) : (
                        <button onClick={async () => { await client.post(`/challenges/${c.slug}/release`); loadData() }}
                          className="text-xs px-2 py-0.5 rounded" style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>Release</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : tab === 'audit' ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-mono" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                <th className="text-left pb-2">Time</th><th className="text-left pb-2">User</th>
                <th className="text-left pb-2">Action</th><th className="text-left pb-2">Details</th>
              </tr>
            </thead>
            <tbody>
              {(Array.isArray(data) ? data : []).map((a, i) => (
                <tr key={a.id || i} style={{ borderTop: '1px solid var(--border)' }}>
                  <td className="py-2 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{new Date(a.created_at).toLocaleString()}</td>
                  <td className="py-2" style={{ color: 'var(--text-secondary)' }}>{a.user_id || '-'}</td>
                  <td className="py-2 font-mono text-xs" style={{ color: 'var(--accent-cyan)' }}>{a.action}</td>
                  <td className="py-2 text-xs truncate max-w-[200px]" style={{ color: 'var(--text-muted)' }}>{JSON.stringify(a.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : tab === 'system' ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                { label: 'API', status: 'ok', color: 'var(--accent-green)' },
                { label: 'Database', status: data.db_status || 'connected', color: 'var(--accent-green)' },
                { label: 'Redis', status: data.redis_status || 'connected', color: 'var(--accent-green)' },
              ].map((s) => (
                <div key={s.label} className="p-3 rounded-lg" style={{ background: 'var(--bg-primary)' }}>
                  <div className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{s.label}</div>
                  <div className="text-sm font-bold mt-1" style={{ color: s.color }}>{s.status}</div>
                </div>
              ))}
            </div>
            <div className="flex gap-3">
              <button onClick={async () => { await client.post('/admin/seed'); loadData(); alert('Challenges seeded!') }}
                className="px-4 py-2 rounded text-sm font-bold" style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
                Seed Challenges
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
