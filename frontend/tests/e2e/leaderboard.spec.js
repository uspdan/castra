// @ts-check
import { test, expect, testFlag } from './fixtures.js'

/**
 * Phase 12 (slice 20) — leaderboard specs.
 *
 * The "highlight my row" feature in ``Leaderboard.jsx:49``:
 *
 *     background: m.user_id === user?.id ? 'rgba(0,200,255,0.05)' : 'transparent'
 *
 * is the regression canary for the slice-19 read-endpoint
 * migration. If a future slice swaps ``/leaderboard`` for
 * ``/api/v1/scoreboard`` (which doesn't surface ``user_id``) or
 * swaps ``/auth/me`` for ``/api/v1/me`` (which doesn't surface
 * ``id``) without rewriting the comparison, this spec fails.
 */

test.describe('Leaderboard', () => {
  test('renders for an authenticated user', async ({ authedUser }) => {
    const { page } = authedUser
    await page.goto('/leaderboard')
    // Page header / table appears.
    await expect(page.locator('text=/rankings|leaderboard/i').first()).toBeVisible()
  })

  test('viewer row is visually distinguished', async ({
    authedUser, api, request,
  }) => {
    const { page, user } = authedUser

    // Put the viewer on the board on purpose. ``/api/v1/scoreboard``
    // returns the top 100 by points and a freshly-registered user has
    // zero, so on any database that has accumulated more than ~100
    // accounts the viewer sorts off the end of the page and this test
    // would fail for a reason that has nothing to do with the
    // highlight. Solving once anchors them near the top regardless of
    // how many idle accounts exist.
    const slug = `e2e-lb-${Date.now().toString(36)}`
    const flag = testFlag('e2e', slug, 'lb')
    const token = await api.adminToken()
    await api.createChallenge(token, {
      slug,
      title: `E2E Leaderboard ${slug}`,
      description: 'Scores the viewer so they render on the board.',
      category: 'web',
      difficulty: 1,
      points: 100,
      team: 'red',
      flag,
      docker_image: 'alpine:3.19',
      docker_port: 8080,
    })
    await api.releaseChallenge(token, slug)

    const solved = await request.post(`/api/v1/challenges/${slug}/submit`, {
      data: { flag },
      headers: { Authorization: `Bearer ${authedUser.tokens.access}` },
    })
    expect(solved.ok()).toBeTruthy()

    await page.goto('/leaderboard')

    // Exactly one row must identify as the viewer's. This is the
    // regression canary described above: if the read-endpoint swap
    // stops surfacing user_id (or /me stops surfacing id), the
    // comparison in Leaderboard.jsx yields false for every row and
    // this count drops to zero.
    const viewerRow = page.locator(
      '[data-testid="leaderboard-row"][data-viewer="true"]'
    )
    await expect(viewerRow).toHaveCount(1, { timeout: 15_000 })
    await expect(viewerRow).toContainText(user.username)

    // ...and the highlight is actually rendered, not just flagged.
    // Compare against a peer row rather than locking the colour value.
    const peerRow = page
      .locator('[data-testid="leaderboard-row"][data-viewer="false"]')
      .first()
    if (await peerRow.count()) {
      const [viewerBg, peerBg] = await Promise.all([
        viewerRow.evaluate((el) => getComputedStyle(el).backgroundColor),
        peerRow.evaluate((el) => getComputedStyle(el).backgroundColor),
      ])
      expect(viewerBg).not.toBe(peerBg)
    }
  })
})
