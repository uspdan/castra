import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Shield, AlertTriangle } from 'lucide-react'
import useAuthStore from '../stores/authStore'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { resetPassword } = useAuthStore()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [done, setDone] = useState(false)

  const token = searchParams.get('token') || ''

  useEffect(() => {
    if (!token) {
      setError('Reset link is missing the token. Request a new one.')
    }
  }, [token])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (loading || !token) return
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setError('')
    setLoading(true)
    try {
      await resetPassword(token, password)
      setDone(true)
      setTimeout(() => navigate('/login'), 2000)
    } catch (err) {
      setError(err.response?.data?.detail || 'Reset failed. The link may have expired.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center grid-bg" style={{ background: 'var(--bg-primary)' }}>
      <div className="w-full max-w-sm rounded-xl p-8 animate-float-up" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
        <div className="text-center mb-8">
          <Shield size={40} className="mx-auto mb-3" style={{ color: 'var(--accent-cyan)' }} />
          <h1 className="text-2xl font-bold" style={{
            background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-red))',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>RESET PASSWORD</h1>
        </div>

        {done ? (
          <div className="space-y-4 text-center">
            <p className="text-sm" style={{ color: 'var(--accent-green)' }}>
              Password updated. Redirecting to sign in...
            </p>
          </div>
        ) : !token ? (
          <div className="space-y-4 text-center">
            <AlertTriangle size={32} className="mx-auto" style={{ color: 'var(--accent-red)' }} />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              {error}
            </p>
            <Link to="/forgot-password" className="inline-block text-sm" style={{ color: 'var(--accent-cyan)' }}>
              Request a new reset link
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Pick a new password. Minimum 8 characters.
            </p>
            <input
              type="password"
              placeholder="New password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              data-testid="reset-password-new"
              minLength={8}
              required
              className="w-full px-4 py-2.5 rounded-lg text-sm"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }}
            />
            <input
              type="password"
              placeholder="Confirm new password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              data-testid="reset-password-confirm"
              minLength={8}
              required
              className="w-full px-4 py-2.5 rounded-lg text-sm"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }}
            />
            {error && <div className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</div>}
            <button
              type="submit"
              disabled={loading}
              data-testid="reset-password-submit"
              className="w-full py-2.5 rounded-lg font-bold text-sm transition-all disabled:opacity-50"
              style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}
            >
              {loading ? 'Resetting...' : 'Set new password'}
            </button>
            <p className="text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              <Link to="/login" style={{ color: 'var(--accent-cyan)' }}>Back to sign in</Link>
            </p>
          </form>
        )}
      </div>
    </div>
  )
}
