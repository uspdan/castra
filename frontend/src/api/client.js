import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Single-flight refresh: when several requests 401 at the same
// moment (token just expired, page fires parallel fetches), only
// the first triggers POST /auth/refresh; the rest await the same
// promise. Without this, the losers race each other and a failed
// straggler can clobber the fresh token with a logout redirect.
let refreshPromise = null

function refreshAccessToken(refreshToken) {
  if (!refreshPromise) {
    // Bare axios (not `client`) so a 401 from the refresh call
    // itself doesn't recurse into this interceptor.
    refreshPromise = axios
      .post(`${client.defaults.baseURL}/api/v1/auth/refresh`, {
        refresh_token: refreshToken,
      })
      .then((res) => {
        const newToken = res.data.access_token
        localStorage.setItem('access_token', newToken)
        return newToken
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const newToken = await refreshAccessToken(refreshToken)
          original.headers.Authorization = `Bearer ${newToken}`
          return client(original)
        } catch {
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          localStorage.removeItem('user')
          window.location.href = '/login'
        }
      }
    }
    return Promise.reject(error)
  }
)

export default client
