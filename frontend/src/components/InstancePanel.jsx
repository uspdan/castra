import { useEffect, useState } from 'react'
import { Square, RotateCcw, Clock } from 'lucide-react'
import useInstanceStore from '../stores/instanceStore'
import { toast } from '../stores/toastStore'

/**
 * Sprint 2 — instance lifecycle panel.
 *
 * Reads the live instance from ``useInstanceStore.byChallenge[slug]``
 * so a reset (which mutates the store) re-renders the panel without
 * the parent component needing to refetch. Falls back to the
 * ``instance`` prop for callers that pass it explicitly.
 *
 * Shows:
 *
 *   * The connection port + a small clock-style countdown to
 *     ``expires_at``.
 *   * A STOP button (DELETE /instances/{id}) — the launcher's
 *     409 / 404 / 412 paths surface as toasts.
 *   * A RESET button (POST /instances/{id}/reset) — bumps the
 *     instance's TTL and replaces the running container.
 *
 * The countdown re-renders every second; the panel wakes the parent
 * (``onCleared``) when the user successfully stops the instance so
 * the parent can swap back to the LAUNCH button.
 */
export default function InstancePanel({ instance, slug, onCleared }) {
  const { stopInstance, resetInstance, byChallenge } = useInstanceStore()
  const [busy, setBusy] = useState(null) // 'stop' | 'reset' | null
  const [now, setNow] = useState(Date.now())

  // Prefer the store-tracked instance for the slug so a reset
  // propagates without parent re-renders. ``instance`` prop is the
  // fallback for callers that haven't migrated yet.
  const live = (slug && byChallenge[slug]) || instance
  if (!live) return null

  // Tick every 1s for the countdown. Cheap; one panel only ever
  // exists per page.
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  const id = live.instance_id || live.id
  const remainingMs = live.expires_at
    ? new Date(live.expires_at).getTime() - now
    : null

  const handleStop = async () => {
    if (busy) return
    setBusy('stop')
    try {
      await stopInstance(id, slug)
      toast({ type: 'success', message: 'Instance stopped.' })
      onCleared?.()
    } catch (err) {
      toast({
        type: 'error',
        message: err.response?.data?.detail || 'Stop failed',
      })
    } finally {
      setBusy(null)
    }
  }

  const handleReset = async () => {
    if (busy) return
    setBusy('reset')
    try {
      const res = await resetInstance(id, slug)
      toast({ type: 'success', message: `Instance reset (port ${res.port}).` })
      // Caller re-renders via instanceStore subscription; no
      // ``onCleared`` here because the instance is still running.
    } catch (err) {
      toast({
        type: 'error',
        message: err.response?.data?.detail || 'Reset failed',
      })
    } finally {
      setBusy(null)
    }
  }

  return (
    <div
      data-testid="instance-panel"
      className="p-3 rounded-lg mb-3"
      style={{
        background: 'var(--bg-primary)',
        border: '1px solid var(--accent-green)',
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <span
          className="text-xs font-mono font-bold"
          style={{ color: 'var(--accent-green)' }}
        >
          INSTANCE RUNNING
        </span>
        {remainingMs !== null && (
          <span
            data-testid="instance-expiry"
            className="flex items-center gap-1 text-[11px] font-mono"
            style={{
              color:
                remainingMs < 60_000
                  ? 'var(--accent-red)'
                  : 'var(--text-muted)',
            }}
          >
            <Clock size={11} /> {formatRemaining(remainingMs)}
          </span>
        )}
      </div>

      <div
        className="text-sm font-mono mb-3"
        style={{ color: 'var(--text-primary)' }}
      >
        Connect to port{' '}
        <strong data-testid="instance-port">{live.port}</strong>
      </div>

      <div className="flex gap-2">
        <button
          data-testid="instance-stop"
          onClick={handleStop}
          disabled={busy !== null}
          className="flex-1 py-1.5 rounded text-xs font-bold flex items-center justify-center gap-1 disabled:opacity-50"
          style={{
            background: 'rgba(255,62,108,0.15)',
            color: 'var(--accent-red)',
            border: '1px solid var(--accent-red)',
          }}
        >
          <Square size={11} /> {busy === 'stop' ? 'STOPPING…' : 'STOP'}
        </button>
        <button
          data-testid="instance-reset"
          onClick={handleReset}
          disabled={busy !== null}
          className="flex-1 py-1.5 rounded text-xs font-bold flex items-center justify-center gap-1 disabled:opacity-50"
          style={{
            background: 'rgba(255,200,0,0.15)',
            color: 'var(--accent-yellow)',
            border: '1px solid var(--accent-yellow)',
          }}
        >
          <RotateCcw size={11} /> {busy === 'reset' ? 'RESETTING…' : 'RESET'}
        </button>
      </div>
    </div>
  )
}

function formatRemaining(ms) {
  if (ms <= 0) return 'EXPIRED'
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}
