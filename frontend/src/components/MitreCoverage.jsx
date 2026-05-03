export default function MitreCoverage({ data = [] }) {
  if (!data.length) return null
  return (
    <div className="rounded-lg p-4" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
      <h3 className="text-sm font-bold mb-3 font-mono" style={{ color: 'var(--text-secondary)' }}>MITRE ATT&CK COVERAGE</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {data.map((item) => {
          const pct = item.coverage || item.solve_percentage || 0
          const barColor = pct > 70 ? 'var(--accent-green)' : pct > 50 ? 'var(--accent-yellow)' : 'var(--accent-red)'
          return (
            <div key={item.tactic || item.technique_id} className="flex items-center gap-2">
              <span className="text-[11px] font-mono w-20 shrink-0" style={{ color: 'var(--text-muted)' }}>
                {item.tactic || item.technique_id}
              </span>
              <div className="flex-1 h-4 rounded-full overflow-hidden" style={{ background: 'var(--bg-primary)' }}>
                <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: barColor }} />
              </div>
              <span className="text-[11px] font-mono w-10 text-right" style={{ color: 'var(--text-muted)' }}>
                {Math.round(pct)}%
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
