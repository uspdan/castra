// @ts-check
import { test, expect } from './fixtures.js'

/**
 * Phase 12 (slice 20) — hint-unlock specs.
 *
 * Drives the v1 ``POST /api/v1/challenges/{slug}/hint`` endpoint
 * through the unlock button on the challenge detail card. Asserts
 * that:
 *
 * 1. Locked hints render as the "Unlock hint (-50% points)" button.
 * 2. Clicking unlocks via the v1 endpoint.
 * 3. The challenge refetch surfaces the unlocked hint text.
 */

async function seedChallengeWithHints(api, request, slug) {
  const token = await api.adminToken()
  await api.createChallenge(token, {
    slug,
    title: `E2E Hint ${slug}`,
    description: 'Hint-bearing challenge for the Playwright suite.',
    category: 'web',
    difficulty: 1,
    points: 100,
    team: 'red',
    flag: 'CTF{REDACTED}',
    docker_image: 'alpine:3.19',
    docker_port: 8080,
    hints: [
      { text: 'First hint reveals the path.', cost: 50 },
      { text: 'Second hint reveals the key.', cost: 50 },
    ],
  })
  await api.releaseChallenge(token, slug)
  return slug
}

test.describe('Hint unlock (v1 endpoint)', () => {
  test('locked hint becomes visible after click', async ({
    authedUser, api, request,
  }) => {
    const slug = `e2e-hint-unlock-${Date.now().toString(36)}`
    await seedChallengeWithHints(api, request, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    await page.locator(`text="E2E Hint ${slug}"`).first().click()

    // Initial state: at least one "Unlock hint" button visible.
    const unlockBtn = page.locator('button:has-text("Unlock hint")').first()
    await expect(unlockBtn).toBeVisible()

    // Click; the page refetches the challenge after the v1 POST.
    await unlockBtn.click()

    // After refetch, the first hint's text should be on the page.
    await expect(
      page.locator('text=/First hint reveals the path/i')
    ).toBeVisible({ timeout: 15_000 })
  })
})
