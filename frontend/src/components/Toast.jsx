import { CheckCircle2, AlertTriangle, Info, X } from 'lucide-react'
import useToastStore from '../stores/toastStore'

/**
 * Sprint 2 — toast viewport.
 *
 * Renders the active toast queue stack-bottom-right. Each toast is
 * dismissable; the store auto-dismisses on its own timer too.
 *
 * Mounted once in Layout.jsx; consumers push via
 * ``toast({ type, message })`` from ``../stores/toastStore``.
 */
export default function ToastViewport() {
  const toasts = useToastStore((s) => s.toasts)
  const dismiss = useToastStore((s) => s.dismiss)

  if (toasts.length === 0) return null

  return (
    <div
      data-testid="toast-viewport"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-[320px] max-w-[calc(100vw-2rem)]"
      role="status"
      aria-live="polite"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onClose={() => dismiss(t.id)} />
      ))}
    </div>
  )
}

function ToastItem({ toast, onClose }) {
  const palette = {
    error: {
      bg: 'rgba(255,62,108,0.1)',
      border: 'var(--accent-red)',
      fg: 'var(--accent-red)',
      Icon: AlertTriangle,
    },
    success: {
      bg: 'rgba(16,185,129,0.1)',
      border: 'var(--accent-green)',
      fg: 'var(--accent-green)',
      Icon: CheckCircle2,
    },
    info: {
      bg: 'rgba(0,200,255,0.1)',
      border: 'var(--accent-cyan)',
      fg: 'var(--accent-cyan)',
      Icon: Info,
    },
  }
  const { bg, border, fg, Icon } = palette[toast.type] || palette.info

  return (
    <div
      data-testid={`toast-${toast.type}`}
      className="rounded-lg p-3 flex items-start gap-2 shadow-lg animate-float-up"
      style={{
        background: bg,
        border: `1px solid ${border}`,
        color: 'var(--text-primary)',
      }}
    >
      <Icon size={16} style={{ color: fg, flexShrink: 0, marginTop: 2 }} />
      <div className="flex-1 text-sm font-mono">{toast.message}</div>
      <button
        onClick={onClose}
        aria-label="Dismiss notification"
        className="opacity-60 hover:opacity-100 transition-opacity"
      >
        <X size={14} style={{ color: 'var(--text-muted)' }} />
      </button>
    </div>
  )
}
