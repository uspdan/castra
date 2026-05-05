import { useEffect, useState } from 'react'
import { X } from 'lucide-react'
import { toast } from '../stores/toastStore'
import client from '../api/client'

/**
 * Sprint 9 Phase A — modal-form for creating + editing challenges.
 *
 * Drives ``POST /api/v1/admin/challenges`` (create mode) or
 * ``PUT /api/v1/admin/challenges/{slug}`` (edit mode). On a
 * successful save, ``onSaved(challenge)`` fires so the Admin
 * Challenges tab can refresh.
 *
 * Edit mode pre-fills the slug + title + everything else from the
 * existing challenge response. ``flag`` is omitted on edit because
 * the backend rejects flag changes once solves exist — surface that
 * via a tooltip rather than letting the user type a flag and then
 * eat a 400.
 */
export default function ChallengeEditor({ mode, initial, onClose, onSaved }) {
  const isEdit = mode === 'edit'
  const [form, setForm] = useState(() => ({
    title: initial?.title || '',
    slug: initial?.slug || '',
    description: initial?.description || '',
    category: initial?.category || 'web',
    team: initial?.team || 'red',
    difficulty: initial?.difficulty || 1,
    points: initial?.points || 100,
    flag: '',
    docker_image: initial?.docker_image || 'alpine:3.19',
    docker_port: initial?.docker_port || 8080,
    docker_config: JSON.stringify(initial?.docker_config || {}, null, 2),
    prerequisite_ids: (initial?.prerequisite_ids || []).join(','),
    hints: JSON.stringify(initial?.hints || [], null, 2),
  }))
  const [saving, setSaving] = useState(false)

  // Lock body scroll while open.
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (saving) return
    setSaving(true)
    try {
      // Pre-parse JSON fields with friendly errors.
      let docker_config
      try { docker_config = JSON.parse(form.docker_config || '{}') }
      catch { throw new Error('docker_config must be valid JSON') }
      let hints
      try { hints = JSON.parse(form.hints || '[]') }
      catch { throw new Error('hints must be valid JSON (list of {text, cost})') }
      const prerequisite_ids = form.prerequisite_ids
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => Number.parseInt(s, 10))
        .filter((n) => Number.isFinite(n))

      const body = {
        title: form.title.trim(),
        description: form.description.trim(),
        category: form.category.trim(),
        team: form.team,
        difficulty: Number.parseInt(form.difficulty, 10),
        points: Number.parseInt(form.points, 10),
        docker_image: form.docker_image.trim(),
        docker_port: Number.parseInt(form.docker_port, 10),
        docker_config,
        prerequisite_ids,
        hints,
      }

      let res
      if (isEdit) {
        // Slug only sent if it changed; flag omitted (backend
        // rejects changes after solves).
        if (form.slug.trim() && form.slug.trim() !== initial.slug) {
          body.slug = form.slug.trim()
        }
        res = await client.put(`/api/v1/admin/challenges/${initial.slug}`, body)
      } else {
        body.slug = form.slug.trim()
        if (!form.flag.trim()) throw new Error('flag is required for new challenges')
        body.flag = form.flag.trim()
        res = await client.post('/api/v1/admin/challenges', body)
      }
      toast({ type: 'success', message: isEdit ? 'Challenge updated.' : 'Challenge created.' })
      onSaved?.(res.data)
      onClose?.()
    } catch (err) {
      toast({
        type: 'error',
        message: err.response?.data?.detail || err.message || 'Save failed',
      })
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.6)' }}
      onClick={onClose}
    >
      <form
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        data-testid="challenge-editor"
        className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-lg p-6"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold" style={{ color: 'var(--text-primary)' }}>
            {isEdit ? `Edit ${initial?.slug}` : 'Create challenge'}
          </h2>
          <button type="button" onClick={onClose}
            className="p-1 rounded" style={{ color: 'var(--text-muted)' }}>
            <X size={18} />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input label="Title" value={form.title} onChange={(v) => set('title', v)} required />
          <Input label="Slug" value={form.slug} onChange={(v) => set('slug', v)} required
            disabled={isEdit && !!initial?.solve_count}
            hint="lowercase alphanumeric + hyphens, length ≥ 2" />
          <Field label="Description" full>
            <textarea
              value={form.description}
              onChange={(e) => set('description', e.target.value)}
              required rows={3}
              className="w-full px-3 py-2 rounded text-sm font-mono"
              style={inputStyle}
            />
          </Field>
          <Input label="Category" value={form.category} onChange={(v) => set('category', v)} required />
          <Select label="Team" value={form.team} onChange={(v) => set('team', v)} options={['red', 'blue']} />
          <Input label="Difficulty (1–5)" type="number" min={1} max={5}
            value={form.difficulty} onChange={(v) => set('difficulty', v)} />
          <Input label="Points (1–10000)" type="number" min={1} max={10000}
            value={form.points} onChange={(v) => set('points', v)} />
          {!isEdit && (
            <Input label="Flag (CTF{REDACTED})" value={form.flag} onChange={(v) => set('flag', v)} required
              hint="must match CTF{REDACTED} format" />
          )}
          <Input label="Docker image" value={form.docker_image} onChange={(v) => set('docker_image', v)} required />
          <Input label="Docker port" type="number" min={1} max={65535}
            value={form.docker_port} onChange={(v) => set('docker_port', v)} />
          <Input label="Prerequisite IDs (comma-separated)" value={form.prerequisite_ids}
            onChange={(v) => set('prerequisite_ids', v)} />
          <Field label="Docker config (JSON)" full>
            <textarea
              value={form.docker_config}
              onChange={(e) => set('docker_config', e.target.value)}
              rows={4}
              className="w-full px-3 py-2 rounded text-xs font-mono"
              style={inputStyle}
            />
          </Field>
          <Field label="Hints (JSON list)" full>
            <textarea
              value={form.hints}
              onChange={(e) => set('hints', e.target.value)}
              rows={3}
              placeholder='[{"text": "Try this first", "cost": 50}]'
              className="w-full px-3 py-2 rounded text-xs font-mono"
              style={inputStyle}
            />
          </Field>
        </div>

        <div className="flex justify-end gap-2 mt-6">
          <button type="button" onClick={onClose}
            className="px-4 py-2 rounded text-sm"
            style={{ background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
            Cancel
          </button>
          <button type="submit" disabled={saving}
            data-testid="challenge-editor-save"
            className="px-4 py-2 rounded text-sm font-bold disabled:opacity-50"
            style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
            {saving ? 'Saving...' : (isEdit ? 'Save changes' : 'Create challenge')}
          </button>
        </div>
      </form>
    </div>
  )
}

const inputStyle = {
  background: 'var(--bg-primary)',
  border: '1px solid var(--border)',
  color: 'var(--text-primary)',
  outline: 'none',
}

function Input({ label, value, onChange, hint, type = 'text', full, ...rest }) {
  return (
    <Field label={label} full={full} hint={hint}>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded text-sm"
        style={inputStyle}
        {...rest}
      />
    </Field>
  )
}

function Select({ label, value, onChange, options }) {
  return (
    <Field label={label}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full px-3 py-2 rounded text-sm"
        style={inputStyle}
      >
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </Field>
  )
}

function Field({ label, hint, full, children }) {
  return (
    <label className={`block ${full ? 'md:col-span-2' : ''}`}>
      <span className="block text-xs mb-1" style={{ color: 'var(--text-muted)' }}>{label}</span>
      {children}
      {hint && <span className="block text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>{hint}</span>}
    </label>
  )
}
