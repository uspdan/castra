import { Flame } from 'lucide-react'

const medals = { 1: { label: 'I', color: '#FFD700' }, 2: { label: 'II', color: '#C0C0C0' }, 3: { label: 'III', color: '#CD7F32' } }

export default function LeaderboardRow({ member, index }) {
  const rank = index + 1
  const medal = medals[rank]
  const isRed = member.team === 'red'

  return (
    <div className="flex items-center gap-4 px-4 py-3 rounded-lg transition-colors hover:bg-white/[0.03]" style={{ borderBottom: '1px solid var(--border)' }}>
      <div className="w-8 text-center font-bold font-mono text-sm" style={{ color: medal?.color || 'var(--text-muted)' }}>
        {medal ? medal.label : rank}
      </div>
      <div className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0" style={{
        background: 'var(--bg-elevated)',
        border: `2px solid ${isRed ? 'var(--accent-red)' : 'var(--accent-cyan)'}`,
        color: 'var(--text-primary)',
      }}>
        {(member.display_name || member.username || '?')[0].toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm truncate" style={{ color: 'var(--text-primary)' }}>{member.display_name || member.username}</div>
      </div>
      <div className="font-bold font-mono text-sm" style={{ color: 'var(--accent-cyan)' }}>
        {(member.total_points || 0).toLocaleString()}
      </div>
      <div className="font-mono text-xs w-12 text-center" style={{ color: 'var(--text-muted)' }}>
        {member.total_solves || 0}
      </div>
      {(member.current_streak || 0) > 0 && (
        <div className="flex items-center gap-1 text-xs font-mono" style={{ color: 'var(--accent-yellow)' }}>
          <Flame size={12} /> {member.current_streak}d
        </div>
      )}
    </div>
  )
}
