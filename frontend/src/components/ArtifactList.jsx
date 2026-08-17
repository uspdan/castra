import { useState } from 'react'
import { Download, FileText, Loader } from 'lucide-react'
import { v1 } from '../api/client'
import { reportIgnored } from '../lib/report'

/**
 * Download list for a challenge's declared artifacts (ADR 005).
 *
 * Rendered in place of the LAUNCH button for artifact-only challenges,
 * and alongside it for container challenges that also ship files.
 *
 * Downloads go through the authenticated axios client rather than a
 * plain <a href>: auth is a Bearer header, and putting the token in a
 * query string instead would land it in every access log — the exact
 * shape of audit finding R11 (WS tokens in URLs), which this codebase
 * already paid to remove once. The cost is that the file is buffered
 * as a Blob before saving; acceptable for the log-bundle sizes
 * artifact challenges actually ship. Revisit with a one-shot download
 * token if multi-GiB artifacts become common.
 */
function humanSize(bytes) {
  if (bytes == null) return ''
  const units = ['B', 'KB', 'MB', 'GB']
  let n = bytes, i = 0
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i += 1 }
  return `${n < 10 && i > 0 ? n.toFixed(1) : Math.round(n)} ${units[i]}`
}

export default function ArtifactList({ slug, artifacts }) {
  const [busyPath, setBusyPath] = useState(null)

  if (!artifacts?.length) return null

  const download = async (path) => {
    if (busyPath) return
    setBusyPath(path)
    try {
      const res = await v1.get(
        `/challenges/${slug}/artifacts/${path}`,
        { responseType: 'blob' },
      )
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = path.split('/').pop()
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (err) {
      reportIgnored(`artifact.download ${slug}/${path}`, err)
    } finally {
      setBusyPath(null)
    }
  }

  return (
    <div className="mt-4" data-testid="artifact-list">
      <h4 className="text-xs font-mono font-bold mb-2" style={{ color: 'var(--text-muted)' }}>
        ARTIFACTS
      </h4>
      {artifacts.map((a) => (
        <button
          key={a.path}
          data-testid="artifact-download"
          onClick={() => download(a.path)}
          disabled={busyPath !== null}
          className="w-full flex items-center gap-2 text-xs p-2 rounded mb-1 hover:bg-white/5 text-left disabled:opacity-50"
          style={{ background: 'var(--bg-primary)', color: 'var(--text-secondary)' }}
        >
          <FileText size={12} />
          <span className="flex-1 truncate">{a.path}</span>
          {a.size_bytes != null && (
            <span style={{ color: 'var(--text-muted)' }}>{humanSize(a.size_bytes)}</span>
          )}
          {busyPath === a.path ? <Loader size={12} className="animate-spin" /> : <Download size={12} />}
        </button>
      ))}
    </div>
  )
}
