import { CheckCircle } from 'lucide-react'
import clsx from 'clsx'

export default function ChallengeCard({ challenge, onClick }) {
  const isRed = challenge.team === 'red'
  const diffColor = challenge.difficulty <= 2 ? 'var(--accent-green)' : challenge.difficulty === 3 ? 'var(--accent-yellow)' : 'var(--accent-red)'

  return (
    <div
      onClick={() => onClick?.(challenge)}
      className="rounded-lg p-4 cursor-pointer transition-all hover:scale-[1.01] group animate-float-up"
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderTop: `3px solid ${isRed ? 'var(--accent-red)' : 'var(--accent-cyan)'}`,
      }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded" style={{
          background: isRed ? 'rgba(255,62,108,0.15)' : 'rgba(0,200,255,0.15)',
          color: isRed ? 'var(--accent-red)' : 'var(--accent-cyan)',
        }}>
          {isRed ? 'ATK' : 'DEF'}
        </span>
        <span className="text-[10px] font-mono" style={{ color: 'var(--text-muted)' }}>{challenge.category}</span>
      </div>

      <h3 className="font-semibold mb-1 line-clamp-1" style={{ color: 'var(--text-primary)', fontFamily: 'Outfit' }}>
        {challenge.title}
      </h3>
      <p className="text-xs line-clamp-2 mb-3" style={{ color: 'var(--text-muted)' }}>
        {challenge.description}
      </p>

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex gap-0.5">
            {[1, 2, 3, 4, 5].map((n) => (
              <div key={n} className="w-2 h-2 rounded-sm" style={{
                background: n <= challenge.difficulty ? diffColor : 'var(--border)',
              }} />
            ))}
          </div>
          <span className="text-sm font-bold font-mono" style={{ color: diffColor }}>
            {challenge.points}pts
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            {challenge.solve_count || 0} solves
          </span>
          {challenge.user_solved && (
            <CheckCircle size={16} style={{ color: 'var(--accent-green)' }} />
          )}
        </div>
      </div>
    </div>
  )
}
