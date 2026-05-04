import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Shield, Mail } from 'lucide-react'
import useAuthStore from '../stores/authStore'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const { forgotPassword } = useAuthStore()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!email.trim() || loading) return
    setError('')
    setLoading(true)
    try {
      await forgotPassword(email.trim())
      setSubmitted(true)
    } catch (err) {
      // The endpoint always returns 202 on a valid email shape;
      // the only realistic failure is rate-limit (429) or
      // schema-rejected input.
      setError(err.response?.data?.detail || 'Could not send reset link')
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
          }}>FORGOT PASSWORD</h1>
        </div>

        {submitted ? (
          <div className="space-y-4 text-center">
            <Mail size={32} className="mx-auto" style={{ color: 'var(--accent-green)' }} />
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              If an account exists for <strong style={{ color: 'var(--text-primary)' }}>{email}</strong>, you'll receive a password-reset link shortly.
            </p>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
              Check your inbox (and spam folder). The link expires in one hour.
            </p>
            <Link to="/login" className="inline-block text-sm mt-4" style={{ color: 'var(--accent-cyan)' }}>
              Back to sign in
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Enter the email address you signed up with. We'll send you a link to reset your password.
            </p>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              data-testid="forgot-password-email"
              required
              className="w-full px-4 py-2.5 rounded-lg text-sm"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }}
            />
            {error && <div className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</div>}
            <button
              type="submit"
              disabled={loading || !email.trim()}
              data-testid="forgot-password-submit"
              className="w-full py-2.5 rounded-lg font-bold text-sm transition-all disabled:opacity-50"
              style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}
            >
              {loading ? 'Sending...' : 'Send reset link'}
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
