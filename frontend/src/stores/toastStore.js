import { create } from 'zustand'

/**
 * Sprint 2 — toast store.
 *
 * Replaces ``alert()`` calls scattered through page-level error
 * handlers. The store keeps a small queue of active toasts; the
 * ``<ToastViewport>`` in Layout.jsx renders them.
 *
 * API:
 *
 *   useToastStore.getState().push({ type: 'error', message: '...' })
 *
 * ``type`` is one of ``error`` / ``success`` / ``info``. ``durationMs``
 * defaults to 4000 (errors stick a touch longer than the eye-blink
 * success messages we'd want for the FlagSubmission success indicator
 * — but FlagSubmission still has its own inline result UI, so this
 * store is mostly used for error and ``info`` events the page can't
 * surface inline).
 */
let _idCounter = 0

const useToastStore = create((set, get) => ({
  toasts: [],

  push: ({ type = 'info', message, durationMs = 4000 } = {}) => {
    if (!message) return null
    _idCounter += 1
    const id = _idCounter
    set((s) => ({
      toasts: [...s.toasts, { id, type, message, createdAt: Date.now() }],
    }))
    if (durationMs > 0) {
      setTimeout(() => get().dismiss(id), durationMs)
    }
    return id
  },

  dismiss: (id) => {
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }))
  },

  clear: () => {
    set({ toasts: [] })
  },
}))

// Convenience export so consumers can ``import { toast } from
// '../stores/toastStore'`` without grabbing the store handle.
export const toast = (...args) => useToastStore.getState().push(...args)

export default useToastStore
