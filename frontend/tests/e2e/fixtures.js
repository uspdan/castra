// @ts-check
import { test as base, expect } from '@playwright/test'

/**
 * Phase 12 (slice 20) — Playwright fixtures.
 *
 * The fixtures in this file:
 *
 * - ``api`` — a small wrapper around ``request.fetch`` that talks to
 *   the platform's REST API for setup steps. The frontend dev server
 *   proxies ``/api/*`` and ``/auth/*`` / ``/challenges/*`` etc. to
 *   the backend (see ``frontend/vite.config.js`` and
 *   ``nginx/default.conf`` in the prod compose), so a single
 *   ``baseURL`` covers both.
 *
 * - ``authedUser`` — registers a fresh per-test user via the API,
 *   then injects the access + refresh tokens + user object into
 *   ``localStorage`` *before* the test navigates anywhere. Faster
 *   and more deterministic than driving the login form for every
 *   test (the form itself has its own dedicated spec).
 *
 * - ``adminUser`` — same shape, but elevates the user's role via
 *   the test seam ``POST /admin/users/{id}`` after registration.
 *   Requires the bootstrap admin's credentials to be available
 *   via ``E2E_ADMIN_EMAIL`` / ``E2E_ADMIN_PASSWORD`` env vars
 *   (default: ``admin@siege.local`` / value of
 *   ``ADMIN_PASSWORD`` env var on the running backend).
 */

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'admin@siege.local'
const ADMIN_PASSWORD =
  process.env.E2E_ADMIN_PASSWORD || process.env.ADMIN_PASSWORD || ''

let _testCounter = 0
function uniqueSuffix() {
  _testCounter += 1
  return `${Date.now().toString(36)}-${_testCounter}`
}

export const test = base.extend({
  /**
   * Authenticated request helper. Use this for setup steps that
   * don't need a browser — registering users, seeding challenges,
   * issuing admin actions.
   */
  api: async ({ request }, use) => {
    const helpers = {
      register: async ({ email, username, password, team = 'red' }) => {
        const res = await request.post('/api/v1/auth/register', {
          data: {
            email,
            username,
            display_name: username,
            password,
            team,
          },
        })
        if (!res.ok()) {
          throw new Error(
            `register failed: ${res.status()} ${await res.text()}`
          )
        }
        return await res.json()
      },

      login: async ({ email, password }) => {
        const res = await request.post('/api/v1/auth/login', {
          data: { email, password },
        })
        if (!res.ok()) {
          throw new Error(
            `login failed: ${res.status()} ${await res.text()}`
          )
        }
        return await res.json()
      },

      adminToken: async () => {
        if (!ADMIN_PASSWORD) {
          throw new Error(
            'ADMIN_PASSWORD env var not set; cannot authenticate as admin'
          )
        }
        const out = await helpers.login({
          email: ADMIN_EMAIL,
          password: ADMIN_PASSWORD,
        })
        return out.access_token
      },

      promoteToAdmin: async (userId) => {
        const token = await helpers.adminToken()
        const res = await request.put(`/api/v1/admin/users/${userId}`, {
          data: { role: 'admin' },
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok()) {
          throw new Error(
            `promoteToAdmin failed: ${res.status()} ${await res.text()}`
          )
        }
      },

      createChallenge: async (token, payload) => {
        const res = await request.post('/api/v1/admin/challenges', {
          data: payload,
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!res.ok()) {
          throw new Error(
            `createChallenge failed: ${res.status()} ${await res.text()}`
          )
        }
        return await res.json()
      },

      releaseChallenge: async (token, slug) => {
        const res = await request.post(
          `/api/v1/admin/challenges/${slug}/release`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        )
        if (!res.ok()) {
          throw new Error(
            `releaseChallenge failed: ${res.status()} ${await res.text()}`
          )
        }
        return await res.json()
      },

      addFlag: async (token, slug, flag) => {
        const res = await request.post(
          `/api/v1/admin/challenges/${slug}/flags`,
          {
            data: flag,
            headers: { Authorization: `Bearer ${token}` },
          }
        )
        if (!res.ok()) {
          throw new Error(
            `addFlag failed: ${res.status()} ${await res.text()}`
          )
        }
        return await res.json()
      },
    }
    await use(helpers)
  },

  /**
   * Registers a fresh user, plants their tokens into localStorage,
   * navigates to the dashboard. The ``page`` is returned authed.
   */
  authedUser: async ({ page, api }, use) => {
    const suffix = uniqueSuffix()
    const credentials = {
      email: `e2e-${suffix}@test.local`,
      username: `e2e_${suffix.replace(/-/g, '_')}`,
      password: 'E2eTestPass!1A',
      team: 'red',
    }
    const auth = await api.register(credentials)

    // Plant the auth state before any client-side script runs so
    // the auth store picks it up on first render. ``addInitScript``
    // executes in every navigated page within the context.
    await page.addInitScript(({ accessToken, refreshToken, user }) => {
      window.localStorage.setItem('access_token', accessToken)
      window.localStorage.setItem('refresh_token', refreshToken)
      window.localStorage.setItem('user', JSON.stringify(user))
    }, {
      accessToken: auth.access_token,
      refreshToken: auth.refresh_token,
      user: auth.user,
    })

    await use({
      page,
      credentials,
      user: auth.user,
      tokens: {
        access: auth.access_token,
        refresh: auth.refresh_token,
      },
    })
  },

  /**
   * Same shape as ``authedUser`` but the user has been elevated to
   * admin role. Requires the bootstrap admin to be reachable; tests
   * that need this fixture skip cleanly when ADMIN_PASSWORD is
   * unset.
   */
  adminUser: async ({ page, api }, use) => {
    if (!ADMIN_PASSWORD) {
      test.skip(
        true,
        'ADMIN_PASSWORD env var not set; admin-only tests skipped'
      )
    }
    const suffix = uniqueSuffix()
    const credentials = {
      email: `admin-e2e-${suffix}@test.local`,
      username: `adm_${suffix.replace(/-/g, '_')}`,
      password: 'E2eAdminPass!1A',
      team: 'red',
    }
    const reg = await api.register(credentials)
    await api.promoteToAdmin(reg.user.id)
    // Re-login so the JWT carries the elevated role claim.
    const fresh = await api.login({
      email: credentials.email,
      password: credentials.password,
    })

    await page.addInitScript(({ accessToken, refreshToken, user }) => {
      window.localStorage.setItem('access_token', accessToken)
      window.localStorage.setItem('refresh_token', refreshToken)
      window.localStorage.setItem('user', JSON.stringify(user))
    }, {
      accessToken: fresh.access_token,
      refreshToken: fresh.refresh_token,
      user: fresh.user,
    })

    await use({
      page,
      credentials,
      user: fresh.user,
      tokens: {
        access: fresh.access_token,
        refresh: fresh.refresh_token,
      },
    })
  },
})

export { expect }
