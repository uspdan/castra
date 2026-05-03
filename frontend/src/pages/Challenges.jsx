import { useEffect, useState, useCallback } from 'react'
import { Search, X, Play, Lock, Unlock } from 'lucide-react'
import useChallengeStore from '../stores/challengeStore'
import useInstanceStore from '../stores/instanceStore'
import ChallengeCard from '../components/ChallengeCard'
import FlagSubmission from '../components/FlagSubmission'
import InstancePanel from '../components/InstancePanel'
import ChallengeProgress from '../components/ChallengeProgress'
import { toast } from '../stores/toastStore'
import client from '../api/client'

export default function Challenges() {
  const { challenges, selectedChallenge, filters, loading, fetchChallenges, fetchChallenge, setFilter, clearSelected } = useChallengeStore()
  const { launchInstance } = useInstanceStore()
  const [searchInput, setSearchInput] = useState('')
  const [instance, setInstance] = useState(null)
  const [launching, setLaunching] = useState(false)
  // Bumps after a successful flag submit so ChallengeProgress
  // refetches the per-flag state without us refetching the whole
  // challenge object on every keystroke.
  const [progressRefresh, setProgressRefresh] = useState(0)

  useEffect(() => { fetchChallenges() }, [filters.team, filters.category, filters.difficulty, filters.sort])

  const debounceSearch = useCallback(() => {
    const timer = setTimeout(() => setFilter('search', searchInput), 300)
    return () => clearTimeout(timer)
  }, [searchInput])
  useEffect(debounceSearch, [searchInput])
  useEffect(() => { if (filters.search) fetchChallenges() }, [filters.search])

  const handleLaunch = async () => {
    if (!selectedChallenge || launching) return
    setLaunching(true)
    try {
      const res = await launchInstance(selectedChallenge.slug)
      setInstance(res)
      toast({ type: 'success', message: `Instance launched on port ${res.port}` })
    } catch (err) {
      toast({
        type: 'error',
        message: err.response?.data?.detail || 'Launch failed',
      })
    } finally {
      setLaunching(false)
    }
  }

  const teams = ['', 'red', 'blue']
  const sortOptions = [
    { value: 'newest', label: 'Newest' },
    { value: 'points', label: 'Points' },
    { value: 'difficulty', label: 'Difficulty' },
    { value: 'solves', label: 'Solves' },
  ]
  const selStyle = { background: 'var(--bg-primary)', border: '1px solid var(--border)', color: 'var(--text-primary)', outline: 'none' }

  return (
    <div className="flex gap-4">
      <div className={`flex-1 ${selectedChallenge ? 'max-w-[calc(100%-380px)]' : ''}`}>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <div className="flex rounded-lg overflow-hidden" style={{ border: '1px solid var(--border)' }}>
            {teams.map((t) => (
              <button key={t} onClick={() => setFilter('team', t)}
                className="px-3 py-1.5 text-xs font-mono font-bold transition-colors"
                style={{
                  background: filters.team === t ? (t === 'red' ? 'rgba(255,62,108,0.2)' : t === 'blue' ? 'rgba(0,200,255,0.2)' : 'rgba(255,255,255,0.1)') : 'var(--bg-surface)',
                  color: filters.team === t ? (t === 'red' ? 'var(--accent-red)' : t === 'blue' ? 'var(--accent-cyan)' : 'var(--text-primary)') : 'var(--text-muted)',
                }}>
                {t === '' ? 'ALL' : t.toUpperCase()}
              </button>
            ))}
          </div>
          <div className="relative flex-1 min-w-[200px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-muted)' }} />
            <input type="text" placeholder="Search challenges..." value={searchInput} onChange={(e) => setSearchInput(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg text-sm" style={selStyle} />
          </div>
          <select value={filters.sort} onChange={(e) => setFilter('sort', e.target.value)} className="px-3 py-1.5 rounded-lg text-sm" style={selStyle}>
            {sortOptions.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[1,2,3,4,5,6].map((i) => <div key={i} className="h-40 rounded-lg animate-pulse" style={{ background: 'var(--bg-surface)' }} />)}
          </div>
        ) : (
          <div className={`grid gap-4 ${selectedChallenge ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1 md:grid-cols-2 xl:grid-cols-3'}`}>
            {challenges.map((c) => <ChallengeCard key={c.id || c.slug} challenge={c} onClick={() => fetchChallenge(c.slug)} />)}
          </div>
        )}
      </div>

      {selectedChallenge && (
        <div className="w-[360px] shrink-0 sticky top-20 h-[calc(100vh-6rem)] overflow-y-auto rounded-lg p-5 animate-float-up"
          style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}>
          <div className="flex items-center justify-between mb-4">
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded" style={{
              background: selectedChallenge.team === 'red' ? 'rgba(255,62,108,0.15)' : 'rgba(0,200,255,0.15)',
              color: selectedChallenge.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)',
            }}>{selectedChallenge.team === 'red' ? 'ATK' : 'DEF'}</span>
            <button onClick={clearSelected}><X size={18} style={{ color: 'var(--text-muted)' }} /></button>
          </div>

          <h2 className="text-lg font-bold mb-1" style={{ color: 'var(--text-primary)' }}>{selectedChallenge.title}</h2>
          <div className="flex items-center gap-2 mb-3">
            <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{selectedChallenge.category}</span>
            <span className="text-xs font-mono font-bold" style={{ color: 'var(--accent-yellow)' }}>{selectedChallenge.points}pts</span>
          </div>

          <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>{selectedChallenge.description}</p>

          {selectedChallenge.skills?.length > 0 && (
            <div className="flex flex-wrap gap-1 mb-3">
              {selectedChallenge.skills.map((s) => (
                <span key={s} className="text-[10px] font-mono px-2 py-0.5 rounded" style={{ background: 'var(--bg-primary)', color: 'var(--text-muted)' }}>{s}</span>
              ))}
            </div>
          )}

          {!instance ? (
            <button onClick={handleLaunch} disabled={launching}
              className="w-full py-2 rounded-lg font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-50"
              style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
              <Play size={14} /> {launching ? 'LAUNCHING...' : 'LAUNCH CHALLENGE'}
            </button>
          ) : (
            <InstancePanel
              instance={instance}
              slug={selectedChallenge.slug}
              onCleared={() => setInstance(null)}
            />
          )}

          <ChallengeProgress slug={selectedChallenge.slug} refreshSeed={progressRefresh} />

          <FlagSubmission
            challengeSlug={selectedChallenge.slug}
            onSuccess={() => {
              fetchChallenges()
              setProgressRefresh((n) => n + 1)
            }}
          />

          {selectedChallenge.hints?.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-mono font-bold mb-2" style={{ color: 'var(--text-muted)' }}>HINTS</h4>
              {selectedChallenge.hints.map((h, i) => (
                <div key={i} className="text-xs p-2 rounded mb-1" style={{ background: 'var(--bg-primary)', color: h.text && h.text !== '{locked}' ? 'var(--text-secondary)' : 'var(--text-muted)' }}>
                  {h.text && h.text !== '{locked}' ? h.text : (
                    <button onClick={async () => {
                      // Phase 12 (slice 18): v1 hint endpoint. Consumer
                      // discards the response shape and refetches the
                      // challenge below to refresh the unlocked-hint state.
                      try { await client.post(`/api/v1/challenges/${selectedChallenge.slug}/hint`); fetchChallenge(selectedChallenge.slug) } catch {}
                    }} className="flex items-center gap-1">
                      <Lock size={12} /> Unlock hint (-50% points)
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
