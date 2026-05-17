import { create } from 'zustand'
import client from '../api/client'

const useChallengeStore = create((set, get) => ({
  challenges: [],
  selectedChallenge: null,
  filters: { team: '', category: '', difficulty: '', search: '', mitre: '', sort: 'newest', status: 'all' },
  loading: false,
  error: null,
  total: 0,
  page: 1,

  fetchChallenges: async (page = 1) => {
    set({ loading: true, error: null })
    try {
      const { filters } = get()
      // 50 per page covers the current full catalogue in a single
      // fetch; backend caps per_page at 100.
      const params = { page, per_page: 50 }
      if (filters.team) params.team = filters.team
      if (filters.category) params.category = filters.category
      if (filters.difficulty) params.difficulty = filters.difficulty
      if (filters.search) params.search = filters.search
      if (filters.mitre) params.mitre = filters.mitre
      if (filters.sort) params.sort = filters.sort
      const res = await client.get('/challenges/', { params })
      set({ challenges: res.data.items || res.data, total: res.data.total || 0, page, loading: false })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },

  fetchChallenge: async (slug) => {
    set({ loading: true, error: null })
    try {
      const res = await client.get(`/challenges/${slug}`)
      set({ selectedChallenge: res.data, loading: false })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },

  setFilter: (key, value) => {
    set((state) => ({ filters: { ...state.filters, [key]: value } }))
  },

  clearFilters: () => {
    set({ filters: { team: '', category: '', difficulty: '', search: '', mitre: '', sort: 'newest', status: 'all' } })
  },

  clearSelected: () => set({ selectedChallenge: null }),
}))

export default useChallengeStore
