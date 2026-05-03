import { create } from 'zustand'
import client from '../api/client'

// Sprint 2 follow-up: lift the per-challenge "current instance" into
// the store so a successful reset propagates to every consumer
// without parent refetches. ``byChallenge`` is keyed by the challenge
// slug (the natural identifier exposed by the v1 catalogue + the
// detail/launch flows). ``instances`` stays as the legacy flat list
// for the dashboard widgets that already iterate it.
const useInstanceStore = create((set, get) => ({
  instances: [],
  byChallenge: {},
  loading: false,

  // Read helper for components that have the slug but not the
  // instance object. Returns ``null`` if no live instance is tracked.
  getForChallenge: (slug) => get().byChallenge[slug] || null,

  fetchInstances: async () => {
    set({ loading: true })
    try {
      const res = await client.get('/instances')
      set({ instances: res.data, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  launchInstance: async (slug) => {
    set({ loading: true })
    try {
      const res = await client.post(`/instances/${slug}/launch`)
      set((s) => ({
        instances: [...s.instances, res.data],
        byChallenge: { ...s.byChallenge, [slug]: res.data },
        loading: false,
      }))
      return res.data
    } catch (err) {
      set({ loading: false })
      throw err
    }
  },

  stopInstance: async (id, slug = null) => {
    try {
      await client.delete(`/instances/${id}`)
      set((s) => {
        const next = { ...s.byChallenge }
        if (slug) {
          delete next[slug]
        } else {
          // Slug not provided: drop any entry whose id matches.
          for (const [k, v] of Object.entries(next)) {
            if (v && (v.id === id || v.instance_id === id)) delete next[k]
          }
        }
        return {
          instances: s.instances.filter((i) => i.id !== id && i.instance_id !== id),
          byChallenge: next,
        }
      })
    } catch (err) {
      throw err
    }
  },

  resetInstance: async (id, slug = null) => {
    set({ loading: true })
    try {
      const res = await client.post(`/instances/${id}/reset`)
      set((s) => {
        const next = { ...s.byChallenge }
        if (slug) {
          next[slug] = res.data
        } else {
          for (const [k, v] of Object.entries(next)) {
            if (v && (v.id === id || v.instance_id === id)) next[k] = res.data
          }
        }
        return {
          instances: s.instances.map((i) => (i.id === id ? res.data : i)),
          byChallenge: next,
          loading: false,
        }
      })
      return res.data
    } catch (err) {
      set({ loading: false })
      throw err
    }
  },
}))

export default useInstanceStore
