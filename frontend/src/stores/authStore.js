import { create } from 'zustand'
import client from '../api/client'

const useAuthStore = create((set, get) => ({
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  accessToken: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),

  get isAuthenticated() {
    return !!get().accessToken
  },

  get isAdmin() {
    return get().user?.role === 'admin'
  },

  login: async (email, password) => {
    const res = await client.post('/api/v1/auth/login', { email, password })
    const { user, access_token, refresh_token } = res.data
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    localStorage.setItem('user', JSON.stringify(user))
    set({ user, accessToken: access_token, refreshToken: refresh_token })
    return user
  },

  register: async (data) => {
    const res = await client.post('/api/v1/auth/register', data)
    const { user, access_token, refresh_token } = res.data
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    localStorage.setItem('user', JSON.stringify(user))
    set({ user, accessToken: access_token, refreshToken: refresh_token })
    return user
  },

  logout: async () => {
    const refreshToken = get().refreshToken
    try {
      await client.post('/api/v1/auth/logout', { refresh_token: refreshToken })
    } catch {}
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user')
    set({ user: null, accessToken: null, refreshToken: null })
  },

  refreshAccessToken: async () => {
    const refreshToken = get().refreshToken
    if (!refreshToken) return
    const res = await client.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
    const newToken = res.data.access_token
    localStorage.setItem('access_token', newToken)
    set({ accessToken: newToken })
  },

  forgotPassword: async (email) => {
    // Always returns 202 with a generic message regardless of
    // whether the email matches a real account. The component
    // doesn't need to know more — show "if an account exists,
    // we sent a link" either way.
    await client.post('/api/v1/auth/forgot-password', { email })
  },

  resetPassword: async (token, newPassword) => {
    await client.post('/api/v1/auth/reset-password', {
      token,
      new_password: newPassword,
    })
  },

  fetchMe: async () => {
    // Phase 12 (slice 21): switched to the locked v1 endpoint.
    // Response shape adds totals (total_points / total_solves /
    // current_streak / rank) — forward-compatible since existing
    // consumers ignore unknown fields. v1 carries `id` since
    // slice 21 so the leaderboard highlight feature still
    // resolves the viewer's own row.
    const res = await client.get('/api/v1/me')
    localStorage.setItem('user', JSON.stringify(res.data))
    set({ user: res.data })
  },
}))

export default useAuthStore
