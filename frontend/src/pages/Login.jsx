import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Shield } from 'lucide-react'
import useAuthStore from '../stores/authStore'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
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
          }}>SIEGE RANGE</h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-2.5 rounded-lg text-sm"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }}
          />
          <input
            type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-2.5 rounded-lg text-sm"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }}
          />
          {error && <div className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</div>}
          <button
            type="submit" disabled={loading}
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
      </div>
    </div>
  )
}
