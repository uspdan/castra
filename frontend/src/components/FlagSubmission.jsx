import { useState } from 'react'
import { Flag } from 'lucide-react'
import client from '../api/client'

export default function FlagSubmission({ challengeSlug, onSuccess }) {
  const [flag, setFlag] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!flag.trim() || loading) return
    setLoading(true)
    setResult(null)
    try {
      // Phase 12 (slice 18): use the locked v1 endpoint. Response
      // shape is forward-compatible (additional optional flag_id /
      // validator fields are ignored here). 4xx mapping is stricter
      // (409 vs 400 for already-solved); the catch reads
      // err.response.data.detail regardless of status code.
      const res = await client.post(`/api/v1/challenges/${challengeSlug}/submit`, { flag: flag.trim() })
      if (res.data.correct) {
        setResult({ type: 'success', message: `FLAG CAPTURED — ${res.data.points_awarded}pts!` })
        onSuccess?.(res.data)
      } else {
        setResult({ type: 'error', message: 'INCORRECT — Try again.' })
      }
    } catch (err) {
      setResult({ type: 'error', message: formatSubmitError(err) })
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Flag size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
          <input
            type="text"
            value={flag}
            onChange={(e) => setFlag(e.target.value)}
            placeholder="CTF{REDACTED}"
            data-testid="flag-input"
            className="w-full pl-9 pr-3 py-2 rounded text-sm font-mono transition-all"
            style={{
              background: 'var(--bg-primary)',
              border: `1px solid ${result?.type === 'success' ? 'var(--accent-green)' : result?.type === 'error' ? 'var(--accent-red)' : 'var(--border)'}`,
              color: 'var(--text-primary)',
              outline: 'none',
            }}
            disabled={loading}
          />
        </div>
        <button
          type="submit"
          disabled={loading || !flag.trim()}
          data-testid="flag-submit"
          className="px-4 py-2 rounded text-sm font-bold transition-all disabled:opacity-50"
          style={{
            background: 'var(--accent-cyan)',
            color: 'var(--bg-primary)',
          }}
        >
          {loading ? '...' : 'SUBMIT'}
        </button>
      </div>
      {result && (
        <div
          data-testid={`flag-result-${result.type}`}
          className="mt-2 text-sm font-mono animate-float-up"
          style={{
            color: result.type === 'success' ? 'var(--accent-green)' : 'var(--accent-red)',
          }}
        >
          {result.message}
        </div>
      )}
    </form>
  )
}

// 412 (PrerequisitesNotMet) returns a structured detail object:
//   { message, missing_slugs: ["foo", "bar"] }
// Other 4xx paths return a plain string. Render the prereq list when
// it is present so users see exactly which challenges they need to
// solve first instead of the generic "prerequisites not met".
function formatSubmitError(err) {
  const detail = err?.response?.data?.detail
  if (detail && typeof detail === 'object' && Array.isArray(detail.missing_slugs)) {
    const missing = detail.missing_slugs
    if (missing.length === 0) {
      return detail.message || 'Submission failed'
    }
    const list = missing.join(', ')
    return `Prerequisites not met — solve first: ${list}`
  }
  if (typeof detail === 'string') return detail
  return 'Submission failed'
}
