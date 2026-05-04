import { useState } from 'react'
import { Save, Key, ShieldAlert, Download, Trash2, ShieldCheck } from 'lucide-react'
import useAuthStore from '../stores/authStore'
import { toast } from '../stores/toastStore'
import client from '../api/client'

/**
 * Settings page — Sprint 7.
 *
 * Three sections:
 *   1. Profile — display_name, team (PATCH /api/v1/auth/profile)
 *   2. REDACTED — change password, MFA enrol/disable
 *   3. Data & danger zone — export account data, delete account
 */
export default function Settings() {
  const { user, setUser } = useAuthStore()

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <header>
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
          Settings
        </h1>
        <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
          Profile, security, and account management for {user?.username}.
        </p>
      </header>

      <ProfileSection user={user} setUser={setUser} />
      <PasswordSection />
      <MfaSection user={user} setUser={setUser} />
      <DangerZoneSection />
    </div>
  )
}

// -----------------------------------------------------------------------------
// Profile
// -----------------------------------------------------------------------------
function ProfileSection({ user, setUser }) {
  const [displayName, setDisplayName] = useState(user?.display_name || '')
  const [team, setTeam] = useState(user?.team || '')
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (saving) return
    setSaving(true)
    try {
      const body = {}
      if (displayName !== (user?.display_name || '')) body.display_name = displayName.trim()
      if (team !== (user?.team || '')) body.team = team || null
      if (Object.keys(body).length === 0) {
        toast({ type: 'info', message: 'Nothing to save.' })
        setSaving(false)
        return
      }
      const res = await client.patch('/api/v1/auth/profile', body)
      setUser?.(res.data)
      toast({ type: 'success', message: 'Profile updated.' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Save failed' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card title="Profile" icon={<Save size={14} />}>
      <Field label="Display name">
        <input
          type="text"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          data-testid="settings-display-name"
          className="w-full px-3 py-2 rounded text-sm"
          style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
        />
      </Field>
      <Field label="Team">
        <select
          value={team}
          onChange={(e) => setTeam(e.target.value)}
          data-testid="settings-team"
          className="w-full px-3 py-2 rounded text-sm"
          style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
        >
          <option value="">— none —</option>
          <option value="red">red</option>
          <option value="blue">blue</option>
        </select>
      </Field>
      <button
        onClick={handleSave}
        disabled={saving}
        data-testid="settings-save-profile"
        className="px-4 py-2 rounded text-sm font-bold disabled:opacity-50"
        style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}
      >
        {saving ? 'Saving...' : 'Save profile'}
      </button>
    </Card>
  )
}

// -----------------------------------------------------------------------------
// Password
// -----------------------------------------------------------------------------
function PasswordSection() {
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirm, setConfirm] = useState('')
  const [saving, setSaving] = useState(false)

  const handleChange = async () => {
    if (saving) return
    if (newPw !== confirm) {
      toast({ type: 'error', message: 'Passwords do not match.' })
      return
    }
    if (newPw.length < 8) {
      toast({ type: 'error', message: 'Password must be at least 8 characters.' })
      return
    }
    setSaving(true)
    try {
      await client.post('/api/v1/auth/change-password', {
        current_password: currentPw,
        new_password: newPw,
      })
      toast({ type: 'success', message: 'Password changed.' })
      setCurrentPw('')
      setNewPw('')
      setConfirm('')
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Change failed' })
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card title="Password" icon={<Key size={14} />}>
      <Field label="Current password">
        <input
          type="password"
          value={currentPw}
          onChange={(e) => setCurrentPw(e.target.value)}
          data-testid="settings-password-current"
          className="w-full px-3 py-2 rounded text-sm"
          style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
        />
      </Field>
      <Field label="New password">
        <input
          type="password"
          value={newPw}
          onChange={(e) => setNewPw(e.target.value)}
          data-testid="settings-password-new"
          className="w-full px-3 py-2 rounded text-sm"
          style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
        />
      </Field>
      <Field label="Confirm new password">
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          data-testid="settings-password-confirm"
          className="w-full px-3 py-2 rounded text-sm"
          style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
        />
      </Field>
      <button
        onClick={handleChange}
        disabled={saving || !currentPw || !newPw || !confirm}
        data-testid="settings-save-password"
        className="px-4 py-2 rounded text-sm font-bold disabled:opacity-50"
        style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}
      >
        {saving ? 'Saving...' : 'Change password'}
      </button>
    </Card>
  )
}

// -----------------------------------------------------------------------------
// MFA — wired in Sprint 7 Phase C
// -----------------------------------------------------------------------------
function MfaSection({ user, setUser }) {
  const [enrolling, setEnrolling] = useState(false)
  const [enrollData, setEnrollData] = useState(null) // {provisioning_uri, secret}
  const [code, setCode] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [disablePw, setDisablePw] = useState('')
  const [disableCode, setDisableCode] = useState('')

  const mfaEnabled = !!user?.mfa_enabled

  const handleStartEnroll = async () => {
    setBusy(true)
    try {
      const res = await client.post('/api/v1/auth/mfa/enroll')
      setEnrollData(res.data)
      setEnrolling(true)
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Enroll failed' })
    } finally {
      setBusy(false)
    }
  }

  const handleConfirm = async () => {
    setBusy(true)
    try {
      const res = await client.post('/api/v1/auth/mfa/confirm', { code })
      setRecoveryCodes(res.data.recovery_codes || [])
      setEnrolling(false)
      setCode('')
      // Refresh user state to pick up mfa_enabled=true.
      const me = await client.get('/api/v1/auth/me')
      setUser?.(me.data)
      toast({ type: 'success', message: 'MFA enabled. Save your recovery codes.' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Code rejected' })
    } finally {
      setBusy(false)
    }
  }

  const handleDisable = async () => {
    setBusy(true)
    try {
      await client.post('/api/v1/auth/mfa/disable', {
        password: disablePw,
        code: disableCode,
      })
      const me = await client.get('/api/v1/auth/me')
      setUser?.(me.data)
      setDisablePw('')
      setDisableCode('')
      toast({ type: 'success', message: 'MFA disabled.' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Disable failed' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Two-factor authentication" icon={<ShieldCheck size={14} />}>
      {recoveryCodes ? (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: 'var(--accent-yellow)' }}>
            Save these recovery codes somewhere safe. Each can be used once if you lose your authenticator.
          </p>
          <pre
            data-testid="settings-mfa-recovery-codes"
            className="p-3 rounded font-mono text-xs whitespace-pre-wrap break-all"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--accent-yellow)', color: 'var(--text-primary)' }}
          >
            {recoveryCodes.join('\n')}
          </pre>
          <button
            onClick={() => setRecoveryCodes(null)}
            className="px-4 py-2 rounded text-sm font-bold"
            style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}
          >
            I've saved them
          </button>
        </div>
      ) : enrolling && enrollData ? (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Scan this QR / paste the secret into your authenticator app, then enter the 6-digit code below.
          </p>
          <div className="text-xs font-mono p-2 rounded break-all" style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
            <strong>Secret:</strong> {enrollData.secret}
          </div>
          <div className="text-xs font-mono p-2 rounded break-all" style={{ background: 'var(--bg-primary)', color: 'var(--text-muted)' }}>
            {enrollData.provisioning_uri}
          </div>
          <Field label="6-digit code">
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              data-testid="settings-mfa-code"
              className="w-full px-3 py-2 rounded text-sm font-mono"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
          </Field>
          <div className="flex gap-2">
            <button
              onClick={handleConfirm}
              disabled={busy || code.length !== 6}
              data-testid="settings-mfa-confirm"
              className="px-4 py-2 rounded text-sm font-bold disabled:opacity-50"
              style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}
            >
              {busy ? 'Verifying...' : 'Confirm + enable'}
            </button>
            <button
              onClick={() => { setEnrolling(false); setEnrollData(null); setCode('') }}
              className="px-4 py-2 rounded text-sm"
              style={{ background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)' }}
            >
              Cancel
            </button>
          </div>
        </div>
      ) : mfaEnabled ? (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: 'var(--accent-green)' }}>
            ✓ MFA is enabled.
          </p>
          <details>
            <summary className="text-sm cursor-pointer" style={{ color: 'var(--accent-red)' }}>
              Disable MFA
            </summary>
            <div className="space-y-2 mt-2">
              <Field label="Current password">
                <input
                  type="password"
                  value={disablePw}
                  onChange={(e) => setDisablePw(e.target.value)}
                  data-testid="settings-mfa-disable-password"
                  className="w-full px-3 py-2 rounded text-sm"
                  style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                />
              </Field>
              <Field label="6-digit code">
                <input
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  value={disableCode}
                  onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, ''))}
                  data-testid="settings-mfa-disable-code"
                  className="w-full px-3 py-2 rounded text-sm font-mono"
                  style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
                />
              </Field>
              <button
                onClick={handleDisable}
                disabled={busy || !disablePw || disableCode.length !== 6}
                data-testid="settings-mfa-disable"
                className="px-4 py-2 rounded text-sm font-bold disabled:opacity-50"
                style={{ background: 'var(--accent-red)', color: 'white' }}
              >
                {busy ? 'Disabling...' : 'Disable MFA'}
              </button>
            </div>
          </details>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            Add a second factor to your account. You'll be asked for a code from your authenticator app each time you sign in.
          </p>
          <button
            onClick={handleStartEnroll}
            disabled={busy}
            data-testid="settings-mfa-enroll"
            className="px-4 py-2 rounded text-sm font-bold disabled:opacity-50"
            style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}
          >
            {busy ? 'Starting...' : 'Enable MFA'}
          </button>
        </div>
      )}
    </Card>
  )
}

// -----------------------------------------------------------------------------
// Danger zone — Sprint 7 Phase B
// -----------------------------------------------------------------------------
function DangerZoneSection() {
  const [exporting, setExporting] = useState(false)
  const [deletePw, setDeletePw] = useState('')
  const [deleting, setDeleting] = useState(false)
  const { logout } = useAuthStore()

  const handleExport = async () => {
    if (exporting) return
    setExporting(true)
    try {
      const res = await client.get('/api/v1/me/data')
      const blob = new Blob([JSON.stringify(res.data, null, 2)], {
        type: 'application/json',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `siege-range-data-${Date.now()}.json`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast({ type: 'success', message: 'Export downloaded.' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Export failed' })
    } finally {
      setExporting(false)
    }
  }

  const handleDelete = async () => {
    if (deleting) return
    if (!deletePw) {
      toast({ type: 'error', message: 'Confirm with your password.' })
      return
    }
    if (!window.confirm('This will anonymise your account. Continue?')) return
    setDeleting(true)
    try {
      await client.request({
        method: 'DELETE',
        url: '/api/v1/me',
        data: { password: deletePw },
      })
      toast({ type: 'success', message: 'Account deleted.' })
      await logout?.()
      window.location.href = '/login'
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'Delete failed' })
      setDeleting(false)
    }
  }

  return (
    <Card title="Data & danger zone" icon={<ShieldAlert size={14} />} accent="red">
      <div className="space-y-3">
        <div>
          <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>
            Download a JSON export of every record we have on you (profile, solves, instances, writeups).
          </p>
          <button
            onClick={handleExport}
            disabled={exporting}
            data-testid="settings-export"
            className="flex items-center gap-2 px-4 py-2 rounded text-sm font-bold disabled:opacity-50"
            style={{ background: 'transparent', color: 'var(--accent-cyan)', border: '1px solid var(--accent-cyan)' }}
          >
            <Download size={14} /> {exporting ? 'Exporting...' : 'Export my data'}
          </button>
        </div>
        <hr style={{ border: 'none', borderTop: '1px solid var(--border)' }} />
        <div>
          <p className="text-sm mb-2" style={{ color: 'var(--accent-red)' }}>
            <strong>Delete account.</strong> Anonymises your profile and revokes all sessions. Solves and audit history are retained but no longer attributed to identifying info.
          </p>
          <Field label="Confirm with current password">
            <input
              type="password"
              value={deletePw}
              onChange={(e) => setDeletePw(e.target.value)}
              data-testid="settings-delete-password"
              className="w-full px-3 py-2 rounded text-sm"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)' }}
            />
          </Field>
          <button
            onClick={handleDelete}
            disabled={deleting || !deletePw}
            data-testid="settings-delete"
            className="flex items-center gap-2 px-4 py-2 rounded text-sm font-bold disabled:opacity-50"
            style={{ background: 'var(--accent-red)', color: 'white' }}
          >
            <Trash2 size={14} /> {deleting ? 'Deleting...' : 'Delete my account'}
          </button>
        </div>
      </div>
    </Card>
  )
}

// -----------------------------------------------------------------------------
// Reusable bits
// -----------------------------------------------------------------------------
function Card({ title, icon, accent = 'cyan', children }) {
  const accentColor = accent === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)'
  return (
    <section
      className="rounded-lg p-5"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
    >
      <h2 className="flex items-center gap-2 text-sm font-mono font-bold mb-4" style={{ color: accentColor }}>
        {icon} {title.toUpperCase()}
      </h2>
      <div className="space-y-3">{children}</div>
    </section>
  )
}

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="block text-xs mb-1" style={{ color: 'var(--text-muted)' }}>
        {label}
      </span>
      {children}
    </label>
  )
}
