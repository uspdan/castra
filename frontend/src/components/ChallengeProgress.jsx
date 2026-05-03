import { useEffect, useState } from 'react'
import { CheckCircle2, Circle, Crown } from 'lucide-react'
import client from '../api/client'

/**
 * Sprint 2 — multi-flag progress strip.
 *
 * Consumes ``GET /api/v1/challenges/{slug}/progress`` (Phase 12
 * slice 3). For multi-flag challenges, renders one chip per flag
 * with captured / uncaptured state + a crown for first-blood
 * captures. For single-flag challenges (the common case), the
 * component renders nothing — there's nothing useful to show that
 * isn't already implied by the FlagSubmission success indicator.
 *
 * The strip refetches whenever ``slug`` changes, on first mount,
 * and via the ``refresh`` ref so FlagSubmission's onSuccess can
 * pull a fresh state. To wire that, the parent passes a
 * ``refreshSeed`` prop that bumps after each submit.
 */
export default function ChallengeProgress({ slug, refreshSeed = 0 }) {
  const [progress, setProgress] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    client
      .get(`/api/v1/challenges/${slug}/progress`)
      .then((res) => {
        if (!cancelled) setProgress(res.data)
      })
      .catch(() => {
        if (!cancelled) setProgress(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [slug, refreshSeed])

  // Single-flag challenges don't benefit from a strip — the
  // FlagSubmission success indicator already tells the user "you
  // got it". Hide.
  if (!progress || progress.total_flags < 2) return null

  const { flags, captured_flags, total_flags, points_captured, total_points_possible, fully_captured } = progress

  return (
    <div
      data-testid="challenge-progress"
      className="my-3 p-3 rounded-lg"
      style={{
        background: 'var(--bg-primary)',
        border: `1px solid ${fully_captured ? 'var(--accent-green)' : 'var(--border)'}`,
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <span
          className="text-[10px] font-mono font-bold"
          style={{
            color: fully_captured ? 'var(--accent-green)' : 'var(--text-muted)',
          }}
        >
          {fully_captured ? 'FULLY CAPTURED' : 'PROGRESS'}
        </span>
        <span
          className="text-[11px] font-mono"
          style={{ color: 'var(--text-muted)' }}
        >
          {captured_flags}/{total_flags} · {points_captured}/{total_points_possible} pts
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {flags.map((f) => (
          <FlagChip key={f.flag_id} flag={f} />
        ))}
      </div>
    </div>
  )
}

function FlagChip({ flag }) {
  const captured = flag.captured
  const firstBlood = !!flag.is_first_blood_flag
  const Icon = captured ? CheckCircle2 : Circle
  const color = captured
    ? firstBlood
      ? 'var(--accent-yellow)'
      : 'var(--accent-green)'
    : 'var(--text-muted)'

  return (
    <span
      data-testid={`flag-chip-${flag.flag_id}`}
      data-captured={captured ? '1' : '0'}
      title={`${flag.label || flag.flag_id} — ${flag.points} pts${
        firstBlood ? ' (first blood)' : ''
      }`}
      className="flex items-center gap-1 text-[11px] font-mono px-2 py-1 rounded"
      style={{
        background:
          captured && firstBlood
            ? 'rgba(255,200,0,0.1)'
            : captured
            ? 'rgba(16,185,129,0.1)'
            : 'var(--bg-surface)',
        border: `1px solid ${color}`,
        color,
      }}
    >
      {firstBlood && captured ? <Crown size={10} /> : <Icon size={10} />}
      <span>{flag.label || flag.flag_id}</span>
      <span style={{ opacity: 0.7 }}>·{flag.points}</span>
    </span>
  )
}
