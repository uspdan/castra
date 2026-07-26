import axios from 'axios'

/**
 * API clients.
 *
 * The backend serves its two API generations at different prefixes:
 * v0 routes sit at the application root (``/challenges``,
 * ``/instances``, ``/admin``, …) and v1 routes sit under ``/api/v1``.
 * Nginx exposes v0 to the browser under ``/api/`` by *stripping* that
 * prefix (``rewrite ^/api/(.*) /$1``), and passes ``/api/v1/`` straight
 * through untouched.
 *
 * There is therefore no single baseURL that addresses both: a base of
 * ``/api`` resolves v0 correctly but turns a v1 path into
 * ``/api/api/v1/…``. That doubled path used to reach the backend only
 * because it missed the ``/api/v1/`` location and fell through to the
 * v0 strip rule — every v1 call in the app was load-bearing on a
 * rewrite that exists for v0. Tightening or reordering those location
 * blocks would have broken the whole frontend at once.
 *
 * Each generation now gets its own base, so both address their real
 * backend path and neither depends on the rewrite.
 */

// Empty (the default) keeps requests origin-relative, which is how the
// app is served behind nginx. Set VITE_API_URL to an absolute origin
// (e.g. http://localhost:8000) to point a bare `vite dev` at the API
// directly, bypassing nginx.
const ORIGIN = import.meta.env.VITE_API_URL || ''

/** v0 — nginx strips ``/api`` back to the backend root. Aimed straight
 *  at the API origin, that root is the origin itself. */
export const V0_BASE = ORIGIN || '/api'

/** v1 — the real backend prefix, which nginx passes through verbatim. */
export const V1_BASE = `${ORIGIN}/api/v1`

const JSON_HEADERS = { 'Content-Type': 'application/json' }

const client = axios.create({ baseURL: V0_BASE, headers: { ...JSON_HEADERS } })
const v1 = axios.create({ baseURL: V1_BASE, headers: { ...JSON_HEADERS } })

function attachAuthHeader(instance) {
  instance.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })
}

function attachRefreshOn401(instance) {
  instance.interceptors.response.use(
    (response) => response,
    async (error) => {
      const original = error.config
      if (error.response?.status === 401 && !original._retry) {
        original._retry = true
        const refreshToken = localStorage.getItem('refresh_token')
        if (refreshToken) {
          try {
            // Refresh always lives on v1, whichever instance 401'd.
            const res = await axios.post(`${V1_BASE}/auth/refresh`, {
              refresh_token: refreshToken,
            })
            const newToken = res.data.access_token
            localStorage.setItem('access_token', newToken)
            original.headers.Authorization = `Bearer ${newToken}`
            // Replay on the instance that failed so the retry keeps
            // that instance's baseURL.
            return instance(original)
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
}

for (const instance of [client, v1]) {
  attachAuthHeader(instance)
  attachRefreshOn401(instance)
}

export { v1 }
export default client
