import { useEffect, useState } from 'react'
import { Terminal, Copy, Power, ExternalLink, Loader2 } from 'lucide-react'
import client from '../api/client'
import { toast } from '../stores/toastStore'

// `/workstation` — per-player analyst container lifecycle.
// Calls into the API surface added in
// `backend/app/routers/v1/workstation.py`. The launch response
// carries a one-shot password the player needs to capture — we
// display it once and never refetch it from the backend.

export default function Workstation() {
  const [status, setStatus] = useState(null)        // { running, ssh_host_port, web_host_port, container }
  const [oneShotPw, setOneShotPw] = useState(null)  // only set right after launch
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    try {
      const res = await client.get('/api/v1/workstation/status')
      setStatus(res.data)
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'status check failed' })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const launch = async () => {
    if (busy) return
    setBusy(true); setOneShotPw(null)
    try {
      const res = await client.post('/api/v1/workstation/launch')
      setStatus({
        running: res.data.running,
        container: res.data.container,
        ssh_host_port: res.data.ssh_host_port,
        web_host_port: res.data.web_host_port,
      })
      if (res.data.one_shot_password) {
        setOneShotPw(res.data.one_shot_password)
      }
      toast({ type: 'success', message: 'workstation up' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'launch failed' })
    } finally {
      setBusy(false)
    }
  }

  const stop = async () => {
    if (busy) return
    if (!window.confirm('Stop your workstation? Your /home is preserved but the SSH session ends.')) return
    setBusy(true); setOneShotPw(null)
    try {
      const res = await client.post('/api/v1/workstation/stop')
      setStatus(res.data)
      toast({ type: 'success', message: 'workstation stopped' })
    } catch (err) {
      toast({ type: 'error', message: err.response?.data?.detail || 'stop failed' })
    } finally {
      setBusy(false)
    }
  }

  const copy = (label, value) => {
    navigator.clipboard?.writeText(value)
    toast({ type: 'success', message: `${label} copied` })
  }

  if (loading) {
    return <div className="p-8 text-center" style={{ color: 'var(--text-muted)' }}>checking workstation status…</div>
  }

  // Prefer the backend-rendered connection strings (the API knows
  // the Host the request came in on and computes them server-side).
  // Fall back to client-side construction if the field is absent.
  const sshHost = window.location.hostname
  const sshCmd = status?.ssh_command ??
    (status?.running ? `ssh -p ${status.ssh_host_port} analyst@${sshHost}` : null)
  const webUrl = status?.web_url ??
    (status?.running ? `http://${sshHost}:${status.web_host_port}/` : null)

  return (
    <div className="max-w-3xl mx-auto py-6 px-4 space-y-4">
      <div className="flex items-center gap-3 mb-2">
        <Terminal size={28} style={{ color: 'var(--accent-cyan)' }} />
        <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Analyst Workstation</h1>
      </div>

      <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
        A container that sits inside the seige-range network with full reachability to every challenge host. Use it
        when you don't have VPN access to your normal forensics toolkit — connect via SSH or browser, run
        <code className="px-1.5 mx-1 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--accent-yellow)' }}>seige list</code>,
        then <code className="px-1.5 mx-1 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--accent-yellow)' }}>ssh dc01</code>
        / <code className="px-1.5 mx-1 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--accent-yellow)' }}>ssh fortigate</code>
        / etc. into each challenge.
      </p>

      <div className="rounded-lg p-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>status</span>
          <span className="text-sm font-mono" style={{
            color: status?.running ? 'var(--accent-green)' : 'var(--text-muted)',
          }}>
            {status?.running ? '● running' : '○ stopped'}
          </span>
        </div>

        {!status?.running && (
          <button onClick={launch} disabled={busy} data-testid="workstation-launch"
            className="w-full py-3 rounded-md font-bold flex items-center justify-center gap-2 disabled:opacity-50"
            style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : <Power size={18} />}
            {busy ? 'launching…' : 'Launch Workstation'}
          </button>
        )}

        {status?.running && (
          <div className="space-y-3">
            <Row label="container">
              <code style={{ color: 'var(--text-primary)' }}>{status.container}</code>
            </Row>
            <Row label="ssh">
              <code style={{ color: 'var(--text-primary)' }}>{sshCmd}</code>
              <button onClick={() => copy('ssh command', sshCmd)} className="ml-2 inline-flex items-center" style={{ color: 'var(--text-muted)' }}>
                <Copy size={14} />
              </button>
            </Row>
            {status.web_host_port && (
              <Row label="web shell">
                <a href={webUrl} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1 underline" style={{ color: 'var(--accent-cyan)' }}>
                  {webUrl} <ExternalLink size={12} />
                </a>
              </Row>
            )}

            {oneShotPw && (
              <div className="mt-3 p-3 rounded" style={{ background: 'rgba(255,200,80,0.08)', border: '1px solid var(--accent-yellow)' }}>
                <div className="text-xs font-mono uppercase mb-1" style={{ color: 'var(--accent-yellow)' }}>
                  one-shot password — capture it now
                </div>
                <div className="flex items-center justify-between">
                  <code className="text-sm" style={{ color: 'var(--text-primary)' }}>{oneShotPw}</code>
                  <button onClick={() => copy('password', oneShotPw)} className="inline-flex items-center text-xs"
                    style={{ color: 'var(--text-muted)' }}>
                    <Copy size={12} /> copy
                  </button>
                </div>
                <div className="text-[11px] mt-2" style={{ color: 'var(--text-muted)' }}>
                  Refreshing this page hides the password. If you lose it, stop and relaunch — your /home volume is
                  preserved, only a fresh password is issued.
                </div>
              </div>
            )}

            <div className="mt-4 p-3 rounded" style={{ background: 'rgba(0,200,255,0.06)', border: '1px solid var(--border)' }}>
              <div className="text-xs font-mono uppercase mb-2" style={{ color: 'var(--accent-cyan)' }}>
                how to connect
              </div>
              <ol className="text-xs space-y-1.5 list-decimal list-inside" style={{ color: 'var(--text-secondary)' }}>
                <li>
                  Open the <strong>web shell</strong> above in a new tab, or paste the <strong>SSH command</strong> into
                  a terminal. Username is <code style={{ color: 'var(--accent-yellow)' }}>analyst</code>; password is
                  the one in the yellow panel.
                </li>
                <li>
                  At the bash prompt run <code style={{ color: 'var(--accent-yellow)' }}>seige list</code> to see every
                  challenge. <em>Or</em> open the platform's Challenges page in another tab and click <strong>Launch</strong>
                  on the one you want to play.
                </li>
                <li>
                  Once a challenge is running, from your workstation type
                  <code className="mx-1 px-1.5 rounded" style={{ background: 'var(--bg-elevated)', color: 'var(--accent-yellow)' }}>
                    ssh &lt;slug&gt;
                  </code>
                  (e.g. <code style={{ color: 'var(--accent-yellow)' }}>ssh dc01</code>,
                  <code style={{ color: 'var(--accent-yellow)' }}> ssh fortigate</code>,
                  <code style={{ color: 'var(--accent-yellow)' }}> ssh tier-2-impact</code>) — the launcher pins the
                  slug as a docker DNS alias and attaches your workstation to that challenge's network automatically.
                  Password at the challenge prompt is <code style={{ color: 'var(--accent-yellow)' }}>hunter</code>.
                </li>
                <li>
                  Submit answers with <code style={{ color: 'var(--accent-yellow)' }}>answer 1 "&lt;value&gt;"</code>
                  inside the challenge, or <code style={{ color: 'var(--accent-yellow)' }}>seige answer &lt;slug&gt; 1 "&lt;value&gt;"</code>
                  from the workstation. <code style={{ color: 'var(--accent-yellow)' }}>seige reveal &lt;slug&gt;</code>
                  prints the flag once every answer is right.
                </li>
              </ol>
            </div>

            <button onClick={stop} disabled={busy} data-testid="workstation-stop"
              className="w-full mt-2 py-2 rounded-md font-mono text-sm disabled:opacity-50"
              style={{ background: 'transparent', border: '1px solid var(--accent-red)', color: 'var(--accent-red)' }}>
              {busy ? 'stopping…' : 'Stop Workstation'}
            </button>
          </div>
        )}
      </div>

      <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
        <strong>What survives a stop:</strong> your <code>/home/analyst</code> — notes, history, scripts, the
        <code className="px-1 mx-1">~/.seige/</code> state file. <strong>What doesn't:</strong> the SSH password
        (rotated every launch), running processes, the workstation's IP.
      </div>
    </div>
  )
}

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-xs font-mono uppercase" style={{ color: 'var(--text-muted)' }}>{label}</span>
      <div className="font-mono">{children}</div>
    </div>
  )
}
