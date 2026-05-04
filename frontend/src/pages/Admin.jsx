import { Fragment, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Users, Trophy, FileText, Activity, Server, Webhook, Trash2,
  RefreshCw, Plus, ChevronLeft, ChevronRight, Search,
} from 'lucide-react'
import useAuthStore from '../stores/authStore'
import { toast } from '../stores/toastStore'
import client from '../api/client'

const tabs = [
  { id: 'users', label: 'Users', icon: Users },
  { id: 'challenges', label: 'Challenges', icon: Trophy },
  { id: 'competitions', label: 'Competitions', icon: Activity },
  { id: 'webhooks', label: 'Webhooks', icon: Webhook },
  { id: 'audit', label: 'Audit', icon: FileText },
  { id: 'system', label: 'System', icon: Server },
]

export default function Admin() {
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()
  const [tab, setTab] = useState('users')

  useEffect(() => {
    if (user?.role !== 'admin') navigate('/')
  }, [user, navigate])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Administration</h1>

      <div className="flex flex-wrap gap-1 rounded-lg p-1" style={{ background: 'var(--bg-surface)' }}>
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(t.id)}
            data-testid={`admin-tab-${t.id}`}
            className="flex items-center gap-2 px-4 py-2 rounded text-sm font-medium transition-colors"
            style={{
              background: tab === t.id ? 'var(--bg-elevated)' : 'transparent',
              color: tab === t.id ? 'var(--accent-cyan)' : 'var(--text-muted)',
            }}>
            <t.icon size={14} /> {t.label}
          </button>
        ))}
      </div>

      <div className="rounded-lg p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
        {tab === 'users' && <UsersTab />}
        {tab === 'challenges' && <ChallengesTab />}
        {tab === 'competitions' && <CompetitionsTab />}
        {tab === 'webhooks' && <WebhooksTab />}
        {tab === 'audit' && <AuditTab />}
        {tab === 'system' && <SystemTab />}
      </div>
    </div>
  )
}

function Loader() {
  return <div className="text-center py-8" style={{ color: 'var(--text-muted)' }}>Loading...</div>
}

function Pagination({ page, perPage, total, onChange }) {
  const totalPages = Math.max(1, Math.ceil((total || 0) / perPage))
  return (
    <div className="flex items-center justify-between mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
      <span className="font-mono">{total || 0} total</span>
      <div className="flex items-center gap-2">
        <button onClick={() => onChange(Math.max(1, page - 1))} disabled={page <= 1}
          className="p-1 rounded disabled:opacity-30">
          <ChevronLeft size={14} />
        </button>
        <span className="font-mono">page {page} / {totalPages}</span>
        <button onClick={() => onChange(Math.min(totalPages, page + 1))} disabled={page >= totalPages}
          className="p-1 rounded disabled:opacity-30">
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------
function UsersTab() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const perPage = 50
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get('/admin/users', { params: { page, per_page: perPage } })
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [page])

  const updateUser = async (id, body) => {
    try {
      await client.put(`/api/v1/admin/users/${id}`, body)
      load()
      toast({ type: 'success', message: 'User updated.' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Update failed' })
    }
  }

  if (loading) return <Loader />

  return (
    <div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] font-mono" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
            <th className="text-left pb-2">User</th>
            <th className="text-left pb-2">Email</th>
            <th className="text-left pb-2">Role</th>
            <th className="text-left pb-2">Team</th>
            <th className="text-right pb-2">Points</th>
            <th className="text-center pb-2">Active</th>
          </tr>
        </thead>
        <tbody>
          {items.map((u) => (
            <tr key={u.id} style={{ borderTop: '1px solid var(--border)' }}>
              <td className="py-2" style={{ color: 'var(--text-primary)' }}>{u.display_name || u.username}</td>
              <td className="py-2 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{u.email}</td>
              <td className="py-2">
                <button onClick={() => updateUser(u.id, { role: u.role === 'admin' ? 'operator' : 'admin' })}
                  className="text-xs font-mono px-2 py-0.5 rounded"
                  style={{
                    background: u.role === 'admin' ? 'rgba(240,180,41,0.15)' : 'var(--bg-primary)',
                    color: u.role === 'admin' ? 'var(--accent-yellow)' : 'var(--text-muted)',
                  }}>{u.role}</button>
              </td>
              <td className="py-2 text-xs" style={{ color: u.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)' }}>{u.team || '-'}</td>
              <td className="py-2 text-right font-mono" style={{ color: 'var(--accent-cyan)' }}>{u.total_points || 0}</td>
              <td className="py-2 text-center">
                <button onClick={() => updateUser(u.id, { is_active: !u.is_active })}
                  className="w-3 h-3 rounded-full"
                  style={{ background: u.is_active ? 'var(--accent-green)' : 'var(--accent-red)' }} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination page={page} perPage={perPage} total={total} onChange={setPage} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Challenges
// ---------------------------------------------------------------------------
function ChallengesTab() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get('/api/v1/challenges', { params: { per_page: 100 } })
      setItems(res.data.items || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const release = async (slug) => {
    try {
      await client.post(`/api/v1/admin/challenges/${slug}/release`)
      toast({ type: 'success', message: 'Released.' })
      load()
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Release failed' })
    }
  }

  const remove = async (slug) => {
    if (!window.confirm(`Soft-delete ${slug}?`)) return
    try {
      await client.delete(`/api/v1/admin/challenges/${slug}`)
      toast({ type: 'success', message: 'Soft-deleted.' })
      load()
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Delete failed' })
    }
  }

  if (loading) return <Loader />

  return (
    <div>
      <div className="flex justify-between mb-3">
        <span className="text-sm font-mono" style={{ color: 'var(--text-muted)' }}>{items.length} challenges</span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] font-mono" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
            <th className="text-left pb-2">Title</th>
            <th className="text-left pb-2">Slug</th>
            <th className="text-left pb-2">Category</th>
            <th className="text-left pb-2">Team</th>
            <th className="text-right pb-2">Points</th>
            <th className="text-center pb-2">Released</th>
            <th className="text-right pb-2"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.slug} style={{ borderTop: '1px solid var(--border)' }}>
              <td className="py-2" style={{ color: 'var(--text-primary)' }}>{c.title}</td>
              <td className="py-2 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{c.slug}</td>
              <td className="py-2 text-xs" style={{ color: 'var(--text-muted)' }}>{c.category}</td>
              <td className="py-2 text-xs" style={{ color: c.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)' }}>{c.team}</td>
              <td className="py-2 text-right font-mono" style={{ color: 'var(--accent-yellow)' }}>{c.points}</td>
              <td className="py-2 text-center">
                {c.released_at ? (
                  <span className="text-xs" style={{ color: 'var(--accent-green)' }}>Live</span>
                ) : (
                  <button onClick={() => release(c.slug)}
                    className="text-xs px-2 py-0.5 rounded"
                    style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>Release</button>
                )}
              </td>
              <td className="py-2 text-right">
                <button onClick={() => remove(c.slug)} title="Soft-delete"
                  className="p-1 rounded" style={{ color: 'var(--accent-red)' }}>
                  <Trash2 size={12} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Competitions
// ---------------------------------------------------------------------------
function CompetitionsTab() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get('/competitions/')
      setItems(res.data || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  if (loading) return <Loader />

  return (
    <div>
      <span className="text-sm font-mono" style={{ color: 'var(--text-muted)' }}>{items.length} competitions</span>
      <table className="w-full text-sm mt-3">
        <thead>
          <tr className="text-[10px] font-mono" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
            <th className="text-left pb-2">Title</th>
            <th className="text-left pb-2">Window</th>
            <th className="text-center pb-2">Live</th>
            <th className="text-right pb-2">Challenges</th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.id} style={{ borderTop: '1px solid var(--border)' }}>
              <td className="py-2" style={{ color: 'var(--text-primary)' }}>{c.title}</td>
              <td className="py-2 font-mono text-xs" style={{ color: 'var(--text-muted)' }}>
                {c.starts_at?.slice(0, 16)} → {c.ends_at?.slice(0, 16)}
              </td>
              <td className="py-2 text-center">
                {c.is_live ? <span style={{ color: 'var(--accent-green)' }}>●</span> : <span style={{ color: 'var(--text-muted)' }}>○</span>}
              </td>
              <td className="py-2 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{c.challenge_count || 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Webhooks — Sprint 8
// ---------------------------------------------------------------------------
function WebhooksTab() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [createdSecret, setCreatedSecret] = useState(null)
  const [selectedId, setSelectedId] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get('/api/v1/webhooks')
      setItems(res.data.items || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const remove = async (id) => {
    if (!window.confirm('Delete this webhook subscription?')) return
    try {
      await client.delete(`/api/v1/webhooks/${id}`)
      toast({ type: 'success', message: 'Deleted.' })
      if (selectedId === id) setSelectedId(null)
      load()
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Delete failed' })
    }
  }

  if (loading && !showCreate) return <Loader />

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-mono" style={{ color: 'var(--text-muted)' }}>{items.length} subscriptions</span>
        <button onClick={() => setShowCreate(true)}
          data-testid="webhooks-new"
          className="flex items-center gap-1 text-xs px-3 py-1 rounded"
          style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
          <Plus size={12} /> New
        </button>
      </div>

      {createdSecret && (
        <div className="rounded p-3 mb-3" style={{ background: 'rgba(240,180,41,0.1)', border: '1px solid var(--accent-yellow)' }}>
          <div className="text-xs font-bold mb-1" style={{ color: 'var(--accent-yellow)' }}>Secret (shown once)</div>
          <pre className="text-xs font-mono break-all" style={{ color: 'var(--text-primary)' }}>{createdSecret}</pre>
          <button onClick={() => setCreatedSecret(null)}
            className="mt-2 text-xs underline" style={{ color: 'var(--text-muted)' }}>Got it</button>
        </div>
      )}

      {showCreate && (
        <CreateWebhookForm onCreated={(secret) => { setCreatedSecret(secret); setShowCreate(false); load() }}
          onCancel={() => setShowCreate(false)} />
      )}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-[10px] font-mono" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
            <th className="text-left pb-2">Name</th>
            <th className="text-left pb-2">Target</th>
            <th className="text-left pb-2">Events</th>
            <th className="text-left pb-2">Last status</th>
            <th className="text-right pb-2"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((w) => (
            <Fragment key={w.id}>
              <tr style={{ borderTop: '1px solid var(--border)' }}>
                <td className="py-2" style={{ color: 'var(--text-primary)' }}>
                  <button onClick={() => setSelectedId(selectedId === w.id ? null : w.id)}
                    style={{ color: 'var(--accent-cyan)' }}>{w.name}</button>
                </td>
                <td className="py-2 font-mono text-xs truncate max-w-[260px]" style={{ color: 'var(--text-muted)' }}>{w.target_url}</td>
                <td className="py-2 text-xs" style={{ color: 'var(--text-muted)' }}>{w.events.join(', ')}</td>
                <td className="py-2 text-xs" style={{ color: w.last_status === 'success' ? 'var(--accent-green)' : w.last_status ? 'var(--accent-red)' : 'var(--text-muted)' }}>
                  {w.last_status || '—'}
                </td>
                <td className="py-2 text-right">
                  <button onClick={() => remove(w.id)} title="Delete"
                    className="p-1 rounded" style={{ color: 'var(--accent-red)' }}>
                    <Trash2 size={12} />
                  </button>
                </td>
              </tr>
              {selectedId === w.id && (
                <tr>
                  <td colSpan={5} className="py-2">
                    <DeliveriesPanel subscriptionId={w.id} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CreateWebhookForm({ onCreated, onCancel }) {
  const [name, setName] = useState('')
  const [targetUrl, setTargetUrl] = useState('')
  const [events, setEvents] = useState('challenge.released')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const res = await client.post('/api/v1/webhooks', {
        name: name.trim(),
        target_url: targetUrl.trim(),
        events: events.split(',').map((s) => s.trim()).filter(Boolean),
      })
      toast({ type: 'success', message: 'Webhook created.' })
      onCreated(res.data.secret)
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Create failed' })
    } finally { setBusy(false) }
  }

  return (
    <form onSubmit={submit} className="space-y-2 mb-4 p-3 rounded" style={{ background: 'var(--bg-primary)' }}>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name"
        className="w-full px-3 py-1.5 rounded text-sm"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} required />
      <input value={targetUrl} onChange={(e) => setTargetUrl(e.target.value)} placeholder="https://example.com/hook"
        type="url"
        className="w-full px-3 py-1.5 rounded text-sm"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} required />
      <input value={events} onChange={(e) => setEvents(e.target.value)}
        placeholder="comma-separated event names (or *)"
        className="w-full px-3 py-1.5 rounded text-sm font-mono"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} required />
      <div className="flex gap-2">
        <button type="submit" disabled={busy}
          className="px-3 py-1.5 rounded text-xs font-bold disabled:opacity-50"
          style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
          {busy ? 'Creating...' : 'Create'}
        </button>
        <button type="button" onClick={onCancel}
          className="px-3 py-1.5 rounded text-xs"
          style={{ background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
          Cancel
        </button>
      </div>
    </form>
  )
}

function DeliveriesPanel({ subscriptionId }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const res = await client.get(`/api/v1/webhooks/${subscriptionId}/deliveries`, { params: { per_page: 20 } })
      setItems(res.data.items || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [subscriptionId])

  const replay = async (deliveryId) => {
    try {
      await client.post(`/api/v1/webhooks/${subscriptionId}/deliveries/${deliveryId}/replay`)
      toast({ type: 'success', message: 'Replayed.' })
      load()
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Replay failed' })
    }
  }

  if (loading) return <Loader />
  if (items.length === 0) return <div className="text-xs py-2" style={{ color: 'var(--text-muted)' }}>No deliveries yet.</div>

  return (
    <div className="rounded p-2" style={{ background: 'var(--bg-primary)' }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Deliveries</span>
        <button onClick={load} className="text-xs flex items-center gap-1" style={{ color: 'var(--text-muted)' }}>
          <RefreshCw size={11} /> Refresh
        </button>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
            <th className="text-left pb-1 font-mono">Time</th>
            <th className="text-left pb-1 font-mono">Event</th>
            <th className="text-left pb-1 font-mono">Status</th>
            <th className="text-right pb-1 font-mono">HTTP</th>
            <th className="text-right pb-1 font-mono">ms</th>
            <th className="text-right pb-1"></th>
          </tr>
        </thead>
        <tbody>
          {items.map((d) => (
            <tr key={d.id} style={{ borderTop: '1px solid var(--border)' }}>
              <td className="py-1 font-mono" style={{ color: 'var(--text-muted)' }}>{d.created_at?.slice(11, 19)}</td>
              <td className="py-1 font-mono" style={{ color: 'var(--accent-cyan)' }}>{d.event_type}</td>
              <td className="py-1" style={{ color: d.status === 'success' ? 'var(--accent-green)' : 'var(--accent-red)' }}>{d.status}</td>
              <td className="py-1 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{d.http_status ?? '-'}</td>
              <td className="py-1 text-right font-mono" style={{ color: 'var(--text-muted)' }}>{d.response_ms ?? '-'}</td>
              <td className="py-1 text-right">
                <button onClick={() => replay(d.delivery_id)}
                  className="text-[10px] px-2 py-0.5 rounded"
                  style={{ background: 'var(--bg-surface)', color: 'var(--accent-cyan)', border: '1px solid var(--accent-cyan)' }}>
                  Replay
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Audit log — pagination + filters
// ---------------------------------------------------------------------------
function AuditTab() {
  const [items, setItems] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const perPage = 50
  const [loading, setLoading] = useState(false)
  const [filterAction, setFilterAction] = useState('')
  const [filterUserId, setFilterUserId] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const params = { page, per_page: perPage }
      if (filterAction) params.action = filterAction
      if (filterUserId) params.user_id = filterUserId
      const res = await client.get('/admin/audit', { params })
      setItems(res.data.items || [])
      setTotal(res.data.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [page, filterAction, filterUserId])

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-3">
        <div className="relative">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
          <input value={filterAction} onChange={(e) => { setFilterAction(e.target.value); setPage(1) }}
            placeholder="event_type contains..."
            data-testid="audit-filter-action"
            className="pl-7 pr-3 py-1 rounded text-xs font-mono"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} />
        </div>
        <input value={filterUserId} onChange={(e) => { setFilterUserId(e.target.value); setPage(1) }}
          placeholder="user_id"
          data-testid="audit-filter-user"
          className="px-3 py-1 rounded text-xs font-mono w-24"
          style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }} />
        <button onClick={load} className="text-xs flex items-center gap-1 px-2" style={{ color: 'var(--text-muted)' }}>
          <RefreshCw size={11} /> Refresh
        </button>
      </div>

      {loading ? <Loader /> : (
        <>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-mono" style={{ color: 'var(--text-muted)', borderBottom: '1px solid var(--border)' }}>
                <th className="text-left pb-2">Time</th>
                <th className="text-left pb-2">User</th>
                <th className="text-left pb-2">Action</th>
                <th className="text-left pb-2">Details</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a, i) => (
                <tr key={a.id || i} style={{ borderTop: '1px solid var(--border)' }}>
                  <td className="py-2 font-mono text-xs whitespace-nowrap" style={{ color: 'var(--text-muted)' }}>
                    {a.created_at ? new Date(a.created_at).toLocaleString() : '-'}
                  </td>
                  <td className="py-2 text-xs" style={{ color: 'var(--text-secondary)' }}>{a.user_id ?? '-'}</td>
                  <td className="py-2 font-mono text-xs" style={{ color: 'var(--accent-cyan)' }}>{a.action}</td>
                  <td className="py-2 text-xs truncate max-w-[400px] font-mono" style={{ color: 'var(--text-muted)' }}>
                    {JSON.stringify(a.details)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={page} perPage={perPage} total={total} onChange={setPage} />
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// System info — wired to /admin/system + /readyz
// ---------------------------------------------------------------------------
function SystemTab() {
  const [info, setInfo] = useState(null)
  const [readiness, setReadiness] = useState(null)
  const [loading, setLoading] = useState(false)
  const [seeding, setSeeding] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [sys, rdy] = await Promise.all([
        client.get('/admin/system'),
        client.get('/readyz').catch((err) => ({ data: err.response?.data || null })),
      ])
      setInfo(sys.data)
      setReadiness(rdy.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const seed = async () => {
    setSeeding(true)
    try {
      const res = await client.post('/api/v1/admin/seed')
      toast({ type: 'success', message: `Seeded ${res.data.created} new (skipped ${res.data.skipped}).` })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Seed failed' })
    } finally { setSeeding(false) }
  }

  if (loading) return <Loader />

  const probes = readiness?.probes || {}

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-xs font-mono mb-2" style={{ color: 'var(--text-muted)' }}>READINESS PROBES</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
          {['postgres', 'redis', 'docker'].map((name) => {
            const p = probes[name]
            const ok = p?.ok
            return (
              <div key={name} className="p-3 rounded" style={{ background: 'var(--bg-primary)' }}>
                <div className="flex items-center justify-between">
                  <div className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>{name}</div>
                  <div className="w-2 h-2 rounded-full" style={{ background: ok ? 'var(--accent-green)' : 'var(--accent-red)' }} />
                </div>
                <div className="text-xs mt-1" style={{ color: ok ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                  {ok ? `ok (${p?.duration_ms}ms)` : (p?.error || 'unknown')}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {info?.db_tables && (
        <div>
          <h3 className="text-xs font-mono mb-2" style={{ color: 'var(--text-muted)' }}>DATABASE</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {Object.entries(info.db_tables).map(([k, v]) => (
              <div key={k} className="p-3 rounded" style={{ background: 'var(--bg-primary)' }}>
                <div className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>{k}</div>
                <div className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>{v}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {info?.containers && (
        <div>
          <h3 className="text-xs font-mono mb-2" style={{ color: 'var(--text-muted)' }}>CONTAINERS</h3>
          <div className="p-3 rounded" style={{ background: 'var(--bg-primary)' }}>
            <div className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>Running</div>
            <div className="text-lg font-bold" style={{
              color: info.containers.running >= 0 ? 'var(--text-primary)' : 'var(--text-muted)',
            }}>
              {info.containers.running >= 0 ? info.containers.running : 'unavailable'}
            </div>
          </div>
        </div>
      )}

      {info?.version && (
        <div className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
          version: {info.version}
        </div>
      )}

      <div className="flex gap-3 pt-2">
        <button onClick={seed} disabled={seeding}
          className="px-4 py-2 rounded text-sm font-bold disabled:opacity-50"
          style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
          {seeding ? 'Seeding...' : 'Seed challenges from /challenges'}
        </button>
        <button onClick={load}
          className="px-4 py-2 rounded text-sm flex items-center gap-1"
          style={{ background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
          <RefreshCw size={12} /> Refresh
        </button>
      </div>
    </div>
  )
}
