/**
 * Surface a deliberately-non-fatal error.
 *
 * Several background fetches (notifications, leaderboard panels, the
 * WebSocket message handler) are best-effort: if they fail the page
 * should carry on rather than break. That was previously expressed as
 * a bare `catch {}`, which also made the failure completely invisible —
 * no console entry, no signal, nothing to grep. CLAUDE.md §2.1 forbids
 * exactly that.
 *
 * This keeps the "carry on" behaviour while making the failure
 * diagnosable. It is not a replacement for handling errors that the
 * user needs to know about — those belong in a toast.
 */
export function reportIgnored(context, err) {
  // eslint-disable-next-line no-console -- this IS the reporting path
  console.warn(`[siege] ${context} failed (ignored):`, err?.message ?? err)
}
