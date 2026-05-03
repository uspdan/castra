import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Play } from 'lucide-react'
import useChallengeStore from '../stores/challengeStore'
import useInstanceStore from '../stores/instanceStore'
import FlagSubmission from '../components/FlagSubmission'
import InstancePanel from '../components/InstancePanel'
import ChallengeProgress from '../components/ChallengeProgress'
import { toast } from '../stores/toastStore'
import client from '../api/client'

export default function ChallengeDetail() {
  const { slug } = useParams()
  const { selectedChallenge, fetchChallenge, loading } = useChallengeStore()
  const { launchInstance } = useInstanceStore()
  const [instance, setInstance] = useState(null)
  const [launching, setLaunching] = useState(false)
  const [progressRefresh, setProgressRefresh] = useState(0)

  useEffect(() => { fetchChallenge(slug) }, [slug])

  const handleLaunch = async () => {
    setLaunching(true)
    try {
      const res = await launchInstance(slug)
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

  if (loading || !selectedChallenge) {
    return <div className="animate-pulse h-96 rounded-lg" style={{ background: 'var(--bg-surface)' }} />
  }

  const c = selectedChallenge
  const isRed = c.team === 'red'

  return (
    <div className="max-w-3xl mx-auto">
      <Link to="/challenges" className="flex items-center gap-1 text-sm mb-4" style={{ color: 'var(--accent-cyan)' }}>
        <ArrowLeft size={14} /> Back to Challenges
      </Link>

      <div className="rounded-lg p-6" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderTop: `3px solid ${isRed ? 'var(--accent-red)' : 'var(--accent-cyan)'}` }}>
        <div className="flex items-center gap-3 mb-4">
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded" style={{
            background: isRed ? 'rgba(255,62,108,0.15)' : 'rgba(0,200,255,0.15)',
            color: isRed ? 'var(--accent-red)' : 'var(--accent-cyan)',
          }}>{isRed ? 'ATK' : 'DEF'}</span>
          <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{c.category}</span>
          <span className="text-xs font-mono font-bold" style={{ color: 'var(--accent-yellow)' }}>{c.points}pts</span>
          <div className="flex gap-0.5 ml-2">
            {[1,2,3,4,5].map((n) => <div key={n} className="w-2 h-2 rounded-sm" style={{ background: n <= c.difficulty ? 'var(--accent-red)' : 'var(--border)' }} />)}
          </div>
        </div>

        <h1 className="text-2xl font-bold mb-4" style={{ color: 'var(--text-primary)' }}>{c.title}</h1>
        <p className="text-sm mb-6 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>{c.description}</p>

        {c.skills?.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-4">
            {c.skills.map((s) => <span key={s} className="text-[10px] font-mono px-2 py-0.5 rounded" style={{ background: 'var(--bg-primary)', color: 'var(--text-muted)' }}>{s}</span>)}
          </div>
        )}

        {c.mitre_techniques?.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-6">
            {c.mitre_techniques.map((t) => <span key={t} className="text-[10px] font-mono px-2 py-0.5 rounded" style={{ background: 'rgba(0,200,255,0.1)', color: 'var(--accent-cyan)' }}>{t}</span>)}
          </div>
        )}

        {!instance ? (
          <button onClick={handleLaunch} disabled={launching}
            className="px-6 py-2.5 rounded-lg font-bold text-sm flex items-center gap-2 disabled:opacity-50"
            style={{ background: 'var(--accent-cyan)', color: 'var(--bg-primary)' }}>
            <Play size={14} /> {launching ? 'LAUNCHING...' : 'LAUNCH CHALLENGE'}
          </button>
        ) : (
          <InstancePanel
            instance={instance}
            slug={c.slug}
            onCleared={() => setInstance(null)}
          />
        )}

        <ChallengeProgress slug={c.slug} refreshSeed={progressRefresh} />

        <FlagSubmission
          challengeSlug={c.slug}
          onSuccess={() => {
            fetchChallenge(slug)
            setProgressRefresh((n) => n + 1)
          }}
        />
      </div>
    </div>
  )
}
