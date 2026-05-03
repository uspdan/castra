import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-primary)' }}>
      <div className="text-center">
        <div className="text-6xl font-bold font-mono mb-4" style={{ color: 'var(--accent-red)' }}>404</div>
        <p className="text-lg mb-6" style={{ color: 'var(--text-muted)' }}>Page not found</p>
        <Link to="/" className="px-4 py-2 rounded-lg text-sm font-bold" style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
          Back to Dashboard
        </Link>
      </div>
    </div>
  )
}
