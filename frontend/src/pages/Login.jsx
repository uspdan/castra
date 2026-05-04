import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Shield, ShieldCheck } from 'lucide-react'
import useAuthStore from '../stores/authStore'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // MFA challenge state — populated after a first-factor login
  // succeeds against an MFA-enabled account. The Login page pivots
  // to a TOTP-input view in that case.
  const [mfaPendingToken, setMfaPendingToken] = useState(null)
  const [mfaCode, setMfaCode] = useState('')

  const { login, verifyMfaLogin } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await login(email, password)
      if (res?.mfaRequired) {
        setMfaPendingToken(res.mfaPendingToken)
        setMfaCode('')
      } else {
        navigate('/')
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleMfaSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await verifyMfaLogin(mfaPendingToken, mfaCode.trim())
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Code rejected')
    } finally {
      setLoading(false)
    }
  }

  const showingMfa = !!mfaPendingToken

  return (
    <div className="min-h-screen flex items-center justify-center grid-bg" style={{ background: 'var(--bg-primary)' }}>
      <div className="w-full max-w-sm rounded-xl p-8 animate-float-up" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
        <div className="text-center mb-8">
          {showingMfa ? (
            <ShieldCheck size={40} className="mx-auto mb-3" style={{ color: 'var(--accent-green)' }} />
          ) : (
            <Shield size={40} className="mx-auto mb-3" style={{ color: 'var(--accent-cyan)' }} />
          )}
          <h1 className="text-2xl font-bold" style={{
            background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-red))',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>{showingMfa ? 'TWO-FACTOR' : 'SIEGE RANGE'}</h1>
        </div>

        {showingMfa ? (
          <form onSubmit={handleMfaSubmit} className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Enter the 6-digit code from your authenticator (or a recovery code).
            </p>
            <input
              type="text"
              autoFocus
              inputMode="text"
              placeholder="123456"
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value.replace(/[^A-Za-z0-9]/g, '').toUpperCase())}
              maxLength={8}
              data-testid="login-mfa-code"
              className="w-full px-4 py-2.5 rounded-lg text-base font-mono text-center tracking-widest"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }}
            />
            {error && <div className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</div>}
            <button
              type="submit"
              disabled={loading || mfaCode.length < 6}
              data-testid="login-mfa-submit"
              className="w-full py-2.5 rounded-lg font-bold text-sm transition-all disabled:opacity-50"
              style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}
            >
              {loading ? 'Verifying...' : 'Verify'}
            </button>
            <button
              type="button"
              onClick={() => { setMfaPendingToken(null); setMfaCode(''); setError('') }}
              className="w-full text-xs"
              style={{ color: 'var(--text-muted)', background: 'transparent', border: 'none' }}
            >
              Use a different account
            </button>
          </form>
        ) : (
          <>
            <form onSubmit={handleSubmit} className="space-y-4">
              <input
                type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
                data-testid="login-email"
                className="w-full px-4 py-2.5 rounded-lg text-sm"
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }}
              />
              <input
                type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)}
                data-testid="login-password"
                className="w-full px-4 py-2.5 rounded-lg text-sm"
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }}
              />
              {error && <div className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</div>}
              <button
                type="submit" disabled={loading}
                data-testid="login-submit"
                className="w-full py-2.5 rounded-lg font-bold text-sm transition-all disabled:opacity-50"
                style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>

            <p className="text-center text-xs mt-4" style={{ color: 'var(--text-muted)' }}>
              <Link to="/forgot-password" style={{ color: 'var(--text-muted)' }}>Forgot password?</Link>
            </p>

            <p className="text-center text-sm mt-2" style={{ color: 'var(--text-muted)' }}>
              No account? <Link to="/register" style={{ color: 'var(--accent-cyan)' }}>Register</Link>
            </p>
          </>
        )}
      </div>
    </div>
  )
}
