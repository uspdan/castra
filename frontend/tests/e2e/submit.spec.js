// @ts-check
import { test, expect } from './fixtures.js'

/**
 * Phase 12 (slice 20) — flag-submission specs.
 *
 * Drives the v1 ``POST /api/v1/challenges/{slug}/submit`` endpoint
 * through the React form (slice 18 migrated the URL). Asserts the
 * happy path, wrong-flag rejection, and the locked 4xx surface
 * (already-solved → 409 with detail string).
 */

async function seedChallenge(api, request, slug) {
  const token = await api.adminToken()
  await api.createChallenge(token, {
    slug,
    title: `E2E Challenge ${slug}`,
    description: 'Spawned by Playwright; safe to delete.',
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

test.describe('Flag submission (v1 endpoint)', () => {
  test('correct flag → success indicator', async ({
    authedUser, api, request,
  }) => {
    const slug = `e2e-submit-ok-${Date.now().toString(36)}`
    await seedChallenge(api, request, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    // The challenges page selects the challenge from the list.
    // Click into it via the title.
    await page.locator(`text="E2E Challenge ${slug}"`).first().click()

    await page.locator('[data-testid="flag-input"]').fill('CTF{REDACTED}')
    await page.locator('[data-testid="flag-submit"]').click()

    await expect(page.locator('[data-testid="flag-result-success"]')).toBeVisible()
    await expect(
      page.locator('[data-testid="flag-result-success"]')
    ).toContainText(/CAPTURED/i)
  })

  test('wrong flag → error indicator', async ({
    authedUser, api, request,
  }) => {
    const slug = `e2e-submit-wrong-${Date.now().toString(36)}`
    await seedChallenge(api, request, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    await page.locator(`text="E2E Challenge ${slug}"`).first().click()

    await page.locator('[data-testid="flag-input"]').fill('CTF{REDACTED}')
    await page.locator('[data-testid="flag-submit"]').click()

    await expect(page.locator('[data-testid="flag-result-error"]')).toBeVisible()
  })

  test('already-solved second submission shows error (409)', async ({
    authedUser, api, request,
  }) => {
    const slug = `e2e-submit-dup-${Date.now().toString(36)}`
    await seedChallenge(api, request, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    await page.locator(`text="E2E Challenge ${slug}"`).first().click()

    // First submission succeeds.
    await page.locator('[data-testid="flag-input"]').fill('CTF{REDACTED}')
    await page.locator('[data-testid="flag-submit"]').click()
    await expect(page.locator('[data-testid="flag-result-success"]')).toBeVisible()

    // Second submission with the same flag — v1 maps to 409 with
    // detail "challenge already solved". The frontend surfaces
    // err.response.data.detail; it shows up as an error result.
    await page.locator('[data-testid="flag-input"]').fill('CTF{REDACTED}')
    await page.locator('[data-testid="flag-submit"]').click()
    await expect(page.locator('[data-testid="flag-result-error"]')).toBeVisible()
    await expect(
      page.locator('[data-testid="flag-result-error"]')
    ).toContainText(/already solved/i)
  })
})
