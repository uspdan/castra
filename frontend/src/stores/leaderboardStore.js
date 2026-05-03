import { create } from 'zustand'
import client from '../api/client'

const useLeaderboardStore = create((set) => ({
  rankings: [],
  teamStats: null,
  weeklyRankings: [],
  loading: false,

  fetchLeaderboard: async (team = '') => {
    // Phase 12 (slice 21): migrated to /api/v1/scoreboard. The v1
    // shape wraps rows in {entries, team_filter, generated_at};
    // unwrap entries here so the consumer (`Leaderboard.jsx`) keeps
    // iterating a flat array. Each entry now carries user_id (added
    // in slice 21) so the "highlight my row" comparison against
    // `useAuthStore().user.id` (also from v1 since slice 21) works.
    set({ loading: true })
    try {
      const params = team ? { team } : {}
      const res = await client.get('/api/v1/scoreboard', { params })
      set({ rankings: res.data?.entries || [], loading: false })
    } catch {
      set({ loading: false })
    }
  },

  fetchTeamStats: async () => {
    // v1 wraps the team rows in {teams, generated_at}. Unwrap to keep
    // existing consumers iterating a flat array.
    try {
      const res = await client.get('/api/v1/leaderboard/teams')
      set({ teamStats: res.data?.teams || [] })
    } catch {}
  },

  fetchWeekly: async () => {
    // v1 wraps in {entries, team_filter, week_start, generated_at}.
    try {
      const res = await client.get('/api/v1/leaderboard/weekly')
      set({ weeklyRankings: res.data?.entries || [] })
    } catch {}
  },
}))

export default useLeaderboardStore
