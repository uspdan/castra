import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Shield, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react'
import client from '../api/client'

export default function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') || ''
  const [state, setState] = useState(token ? 'pending' : 'missing')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    let cancelled = false
    ;(async () => {
      try {
        await client.post('/api/v1/auth/verify-email', { token })
        if (!cancelled) setState('ok')
      } catch (err) {
        if (cancelled) return
        setError(err.response?.data?.detail || 'Verification failed.')
        setState('error')
      }
    })()
    return () => { cancelled = true }
  }, [token])

  return (
    <div className="min-h-screen flex items-center justify-center grid-bg" style={{ background: 'var(--bg-primary)' }}>
      <div className="w-full max-w-sm rounded-xl p-8 text-center animate-float-up"
        style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
        <Shield size={36} className="mx-auto mb-3" style={{ color: 'var(--accent-cyan)' }} />
        <h1 className="text-xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>VERIFY EMAIL</h1>

        {state === 'missing' && (
          <>
            <AlertTriangle size={28} className="mx-auto mb-2" style={{ color: 'var(--accent-red)' }} />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              The verification link is missing the token. Open the link from your email exactly as received, or request a new one from the Settings page.
            </p>
          </>
        )}
        {state === 'pending' && (
          <>
            <Loader2 size={28} className="mx-auto mb-2 animate-spin" style={{ color: 'var(--accent-cyan)' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Verifying...</p>
          </>
        )}
        {state === 'ok' && (
          <>
            <CheckCircle2 size={28} className="mx-auto mb-2" style={{ color: 'var(--accent-green)' }} />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Email verified — you're good to go.
            </p>
            <button onClick={() => navigate('/')}
              className="mt-4 px-4 py-2 rounded text-sm font-bold"
              style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
              Continue to dashboard
            </button>
          </>
        )}
        {state === 'error' && (
          <>
            <AlertTriangle size={28} className="mx-auto mb-2" style={{ color: 'var(--accent-red)' }} />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{error}</p>
            <Link to="/" className="block mt-4 text-sm" style={{ color: 'var(--accent-cyan)' }}>
              Back to dashboard
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
