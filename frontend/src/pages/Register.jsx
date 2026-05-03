import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Shield } from 'lucide-react'
import useAuthStore from '../stores/authStore'

export default function Register() {
  const [form, setForm] = useState({ email: '', username: '', display_name: '', password: '', confirm: '', team: 'red' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register } = useAuthStore()
  const navigate = useNavigate()

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (form.password !== form.confirm) { setError('Passwords do not match'); return }
    if (form.password.length < 8) { setError('Password must be at least 8 characters'); return }
    setLoading(true)
    try {
      await register({ email: form.email, username: form.username, display_name: form.display_name, password: form.password, team: form.team })
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = { background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }

  return (
    <div className="min-h-screen flex items-center justify-center grid-bg" style={{ background: 'var(--bg-primary)' }}>
      <div className="w-full max-w-sm rounded-xl p-8 animate-float-up" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
        <div className="text-center mb-6">
          <Shield size={32} className="mx-auto mb-2" style={{ color: 'var(--accent-cyan)' }} />
          <h1 className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>Create Account</h1>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input type="email" placeholder="Email" value={form.email} onChange={set('email')} className="w-full px-4 py-2 rounded-lg text-sm" style={inputStyle} />
          <input type="text" placeholder="Username" value={form.username} onChange={set('username')} className="w-full px-4 py-2 rounded-lg text-sm" style={inputStyle} />
          <input type="text" placeholder="Display Name" value={form.display_name} onChange={set('display_name')} className="w-full px-4 py-2 rounded-lg text-sm" style={inputStyle} />
          <input type="password" placeholder="Password" value={form.password} onChange={set('password')} className="w-full px-4 py-2 rounded-lg text-sm" style={inputStyle} />
          <input type="password" placeholder="Confirm Password" value={form.confirm} onChange={set('confirm')} className="w-full px-4 py-2 rounded-lg text-sm" style={inputStyle} />

          <div className="flex gap-4 py-2">
            {['red', 'blue'].map((t) => (
              <label key={t} className="flex items-center gap-2 cursor-pointer text-sm" style={{ color: 'var(--text-secondary)' }}>
                <input type="radio" name="team" value={t} checked={form.team === t} onChange={set('team')} />
                <span style={{ color: t === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)' }}>
                  {t === 'red' ? 'Red Team' : 'Blue Team'}
                </span>
              </label>
            ))}
          </div>

          {error && <div className="text-sm" style={{ color: 'var(--accent-red)' }}>{error}</div>}
          <button type="submit" disabled={loading} className="w-full py-2.5 rounded-lg font-bold text-sm disabled:opacity-50" style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
            {loading ? 'Creating...' : 'Create Account'}
          </button>
        </form>

        <p className="text-center text-sm mt-4" style={{ color: 'var(--text-muted)' }}>
          Have an account? <Link to="/login" style={{ color: 'var(--accent-cyan)' }}>Sign In</Link>
        </p>
      </div>
    </div>
  )
}
