// @ts-check
import { test, expect } from './fixtures.js'

/**
 * Sprint 2 follow-up — challenge progress strip.
 *
 * The ``ChallengeProgress`` component (``components/ChallengeProgress.jsx``)
 * renders a per-flag chip strip for multi-flag challenges via
 * ``GET /api/v1/challenges/{slug}/progress``. For single-flag
 * challenges the strip is hidden (``total_flags < 2``).
 *
 * These specs:
 *   1. Seed a 2-flag challenge via the v1 admin write surface.
 *   2. Open the challenge detail page as an authed user.
 *   3. Assert the progress strip is visible with one chip per flag,
 *      both initially uncaptured.
 */

async function seedMultiFlag(api, slug) {
  const token = await api.adminToken()
  await api.createChallenge(token, {
    slug,
    title: `E2E Multi-flag ${slug}`,
    description: 'Two-flag challenge for the Playwright suite.',
    category: 'web',
    difficulty: 1,
    points: 100,
    team: 'red',
    flag: 'CTF{REDACTED}',
    docker_image: 'alpine:3.19',
    docker_port: 8080,
  })
  await api.releaseChallenge(token, slug)
  // Replace the seed flag with two typed flags via the v1 admin
  // flag-add endpoint. Once the first flag is added the legacy
  // single-flag hash is cleared on the backend (see
  // /api/v1/admin/challenges/{slug}/flags).
  await api.addFlag(token, slug, {
    flag_id: 'first',
    flag_type: 'exact',
    points: 50,
    label: 'First',
    value: 'CTF{REDACTED}',
  })
  await api.addFlag(token, slug, {
    flag_id: 'second',
    flag_type: 'exact',
    points: 50,
    label: 'Second',
    value: 'CTF{REDACTED}',
  })
  return slug
}

test.describe('Multi-flag challenge progress strip', () => {
  test('renders one chip per flag for an authed user', async ({
    authedUser, api,
  }) => {
    const slug = `e2e-progress-${Date.now().toString(36)}`
    await seedMultiFlag(api, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    // Open the detail panel from the catalogue list.
    await page.locator(`text="E2E Multi-flag ${slug}"`).first().click()

    const strip = page.locator('[data-testid="challenge-progress"]')
    await expect(strip).toBeVisible({ timeout: 10_000 })

    // One chip per flag, both uncaptured.
    const firstChip = page.locator('[data-testid="flag-chip-first"]')
    const secondChip = page.locator('[data-testid="flag-chip-second"]')
    await expect(firstChip).toBeVisible()
    await expect(secondChip).toBeVisible()
    await expect(firstChip).toHaveAttribute('data-captured', '0')
    await expect(secondChip).toHaveAttribute('data-captured', '0')
  })

  test('chip flips to captured after a successful submit', async ({
    authedUser, api,
  }) => {
    const slug = `e2e-progress-cap-${Date.now().toString(36)}`
    await seedMultiFlag(api, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    await page.locator(`text="E2E Multi-flag ${slug}"`).first().click()

    await expect(
      page.locator('[data-testid="flag-chip-first"]')
    ).toHaveAttribute('data-captured', '0')

    await page.locator('[data-testid="flag-input"]').fill('CTF{REDACTED}')
    await page.locator('[data-testid="flag-submit"]').click()
    await expect(
      page.locator('[data-testid="flag-result-success"]')
    ).toBeVisible()

    // The strip refetches after the parent bumps progressRefresh.
    await expect(
      page.locator('[data-testid="flag-chip-first"]')
    ).toHaveAttribute('data-captured', '1', { timeout: 10_000 })
    // Second flag still uncaptured.
    await expect(
      page.locator('[data-testid="flag-chip-second"]')
    ).toHaveAttribute('data-captured', '0')
  })
})
