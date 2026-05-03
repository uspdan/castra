import { Cpu, HardDrive, MemoryStick, CheckCircle, Shield } from 'lucide-react'

export default function Deploy() {
  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>Deployment Guide</h1>

      <section>
        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--accent-cyan)' }}>System Requirements</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { icon: Cpu, label: 'CPU', value: '4+ cores', desc: 'For concurrent challenge containers' },
            { icon: MemoryStick, label: 'RAM', value: '16 GB min', desc: '8GB for services, 8GB for challenges' },
            { icon: HardDrive, label: 'Disk', value: '50 GB SSD', desc: 'Docker images + database + logs' },
          ].map((r) => (
            <div key={r.label} className="rounded-lg p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
              <r.icon size={24} className="mb-2" style={{ color: 'var(--accent-cyan)' }} />
              <div className="font-bold" style={{ color: 'var(--text-primary)' }}>{r.value}</div>
              <div className="text-xs" style={{ color: 'var(--text-muted)' }}>{r.desc}</div>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--accent-cyan)' }}>Quick Start</h2>
        <div className="rounded-lg p-6 font-mono text-sm leading-7" style={{ background: '#0a0a0a', border: '1px solid var(--border)', color: 'var(--accent-green)' }}>
          <div><span style={{ color: 'var(--text-muted)' }}># Clone and configure</span></div>
          <div>$ git clone &lt;repo-url&gt; && cd seige-range</div>
          <div>$ cp .env.example .env</div>
          <div>$ nano .env  <span style={{ color: 'var(--text-muted)' }}># Set SECRET_KEY and admin credentials</span></div>
          <div>&nbsp;</div>
          <div><span style={{ color: 'var(--text-muted)' }}># Start all services</span></div>
          <div>$ docker compose up -d</div>
          <div>&nbsp;</div>
          <div><span style={{ color: 'var(--text-muted)' }}># Wait for initialization, then seed challenges</span></div>
          <div>$ sleep 30</div>
          <div>$ python scripts/seed_challenges.py</div>
          <div>&nbsp;</div>
          <div><span style={{ color: 'var(--text-muted)' }}># Access dashboard</span></div>
          <div>$ open http://localhost:3000</div>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--accent-cyan)' }}>Architecture</h2>
        <div className="rounded-lg p-6 font-mono text-xs leading-5" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
          <pre>{`
         :3000
           |
        [nginx] ─── rate limiting + security headers
        /     \\
  [dashboard] [api] ──── [redis]
    (Vite)  (FastAPI) ─── [db] (PostgreSQL)
                  \\
              [orchestrator] (Docker-in-Docker)
                  |
          [challenge containers]
                  |
               [vpn] (WireGuard)
          `}</pre>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--accent-cyan)' }}>
          <Shield size={20} className="inline mr-2" />Host Isolation
        </h2>
        <div className="space-y-2">
          {[
            'Read-only root filesystem on all challenge containers',
            'All Linux capabilities dropped (CAP_DROP ALL)',
            'Seccomp: no-new-privileges enforced',
            'Memory limit: 512MB per container',
            'CPU quota: 1 core per container',
            'PID limit: 256 processes max',
            'Network isolation via dedicated Docker networks',
            'Automatic container teardown after timeout (default 2h)',
            'Only the orchestrator runs privileged (DinD)',
            'tmpfs mounts for /tmp and /var/log (size-limited)',
          ].map((item) => (
            <div key={item} className="flex items-start gap-2 text-sm" style={{ color: 'var(--text-secondary)' }}>
              <CheckCircle size={16} className="shrink-0 mt-0.5" style={{ color: 'var(--accent-green)' }} />
              {item}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-bold mb-4" style={{ color: 'var(--accent-cyan)' }}>VPN Setup</h2>
        <div className="rounded-lg p-4 text-sm space-y-2" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
          <p>WireGuard VPN provides direct network access to challenge containers on the internal <code className="font-mono px-1 rounded" style={{ background: 'var(--bg-primary)' }}>10.13.13.0/24</code> subnet.</p>
          <p>Peer configs are generated at startup. Retrieve them from the VPN volume:</p>
          <pre className="font-mono text-xs p-3 rounded mt-2" style={{ background: 'var(--bg-primary)', color: 'var(--accent-green)' }}>
            docker compose exec vpn cat /config/peer1/peer1.conf
          </pre>
          <p className="mt-2">Import the config into any WireGuard client (macOS, Windows, Linux, iOS, Android).</p>
        </div>
      </section>
    </div>
  )
}
