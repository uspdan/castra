// @ts-check
import { test, expect } from './fixtures.js'

test.describe('Login flow', () => {
  test('register → login → dashboard renders', async ({ page, api }) => {
    const suffix = `login-${Date.now().toString(36)}`
    const creds = {
      email: `${suffix}@test.local`,
      username: suffix.replace(/-/g, '_'),
      password: 'LoginTest!1A',
      team: 'red',
    }
    await api.register(creds)

    // Drive the form rather than injecting tokens — this spec is
    // the only one that tests the *form* behaviour end-to-end.
    await page.goto('/login')
    await page.locator('input[type="email"]').fill(creds.email)
    await page.locator('input[type="password"]').fill(creds.password)
    await page.locator('button[type="submit"]').click()

    // After login we navigate to '/'; the layout's nav is the
    // canary that tells us we got past the login screen.
    await expect(page).toHaveURL(/\/$/)
    await expect(page.getByRole('link', { name: /^Challenges$/ })).toBeVisible()
  })

  test('wrong password shows error', async ({ page, api }) => {
    const creds = {
      email: `wrongpw-${Date.now().toString(36)}@test.local`,
      username: `wrongpw_${Date.now().toString(36)}`.replace(/-/g, '_'),
      password: 'CorrectPass!1A',
      team: 'red',
    }
    await api.register(creds)

    await page.goto('/login')
    await page.locator('input[type="email"]').fill(creds.email)
    await page.locator('input[type="password"]').fill('WrongPass!1B')
    await page.locator('button[type="submit"]').click()

    // Stay on /login; error text rendered.
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.locator('text=/incorrect|invalid|failed/i')).toBeVisible()
  })

  test('logout clears session', async ({ authedUser }) => {
    const { page } = authedUser
    await page.goto('/')
    // Open the user-menu dropdown, then click Logout. Both elements
    // are addressed by data-testid (see Layout.jsx) so the spec
    // doesn't drift with copy or icon-class changes.
    await page.locator('[data-testid="user-menu-trigger"]').click()
    await page.locator('[data-testid="user-menu-logout"]').click()
    await expect(page).toHaveURL(/\/login$/)
    const tokens = await page.evaluate(() => ({
      access: window.localStorage.getItem('access_token'),
      refresh: window.localStorage.getItem('refresh_token'),
    }))
    expect(tokens.access).toBeNull()
    expect(tokens.refresh).toBeNull()
  })
})
