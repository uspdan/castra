// @ts-check
import { test, expect } from './fixtures.js'

/**
 * Sprint 2 follow-up — instance lifecycle panel.
 *
 * A full lifecycle test (launch → STOP → RESET) requires a working
 * docker socket on the e2e runner, which is environment-dependent.
 * This spec covers the scenarios that exercise the panel's render
 * + error paths without needing docker:
 *
 *   1. With no running instance, the LAUNCH button is shown and
 *      the panel is hidden.
 *   2. Clicking LAUNCH triggers the v1 launcher; whether docker is
 *      available or not, the result is observable (success toast +
 *      panel render, OR error toast). We assert the deterministic
 *      half: the LAUNCH button toggles into a loading state.
 *
 * Tests that need a fully-running docker stack should run against
 * ``make dev`` locally; the CI worker on the basic test job
 * intentionally stops short of the full launch.
 */

async function seedSingleFlag(api, slug) {
  const token = await api.adminToken()
  await api.createChallenge(token, {
    slug,
    title: `E2E Panel ${slug}`,
    description: 'For the InstancePanel render specs.',
    category: 'web',
    difficulty: 1,
    points: 100,
    team: 'red',
    flag: 'CTF{REDACTED}',
    docker_image: 'alpine:3.19',
    docker_port: 8080,
  })
  await api.releaseChallenge(token, slug)
  return slug
}

test.describe('Instance panel render paths', () => {
  test('LAUNCH button shows for an unlaunched challenge', async ({
    authedUser, api,
  }) => {
    const slug = `e2e-panel-prelaunch-${Date.now().toString(36)}`
    await seedSingleFlag(api, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    await page.locator(`text="E2E Panel ${slug}"`).first().click()

    // Panel hidden, LAUNCH button visible.
    await expect(
      page.locator('[data-testid="instance-panel"]')
    ).toHaveCount(0)
    await expect(
      page.locator('button:has-text("LAUNCH CHALLENGE")')
    ).toBeVisible()
  })

  test('LAUNCH click reaches the loading state', async ({
    authedUser, api,
  }) => {
    const slug = `e2e-panel-loading-${Date.now().toString(36)}`
    await seedSingleFlag(api, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    await page.locator(`text="E2E Panel ${slug}"`).first().click()

    const launchBtn = page.locator(
      'button:has-text("LAUNCH CHALLENGE"), button:has-text("LAUNCHING")'
    ).first()
    await expect(launchBtn).toBeVisible()
    await launchBtn.click()

    // After click: either the LAUNCHING text appears (loading) or a
    // toast surfaces (success or error). Either is acceptable; both
    // confirm the click handler ran.
    const toast = page.locator(
      '[data-testid="toast-success"], [data-testid="toast-error"]'
    )
    const launching = page.locator('button:has-text("LAUNCHING")')
    await expect(toast.or(launching).first()).toBeVisible({
      timeout: 15_000,
    })
  })
})
