// @ts-check
import { execSync } from 'node:child_process'
import { test, expect } from './fixtures.js'

/**
 * Sprint 4 follow-on — full ``InstancePanel`` lifecycle.
 *
 * Drives the launcher through a real docker socket:
 *
 *   click LAUNCH → InstancePanel renders → click STOP → LAUNCH
 *   button reappears.
 *
 *   click LAUNCH → click RESET → port changes → click STOP.
 *
 * The launcher refuses to start a container without a pinned image
 * digest (``MissingImageDigest`` → 409). The spec resolves the
 * ``alpine:3.19`` digest via ``docker inspect`` at setup time and
 * threads it through ``docker_config.digest`` on the seeded
 * challenge. If ``docker`` is not available on the runner — or
 * ``alpine:3.19`` cannot be pulled — every test in this file is
 * skipped with a clear reason. Use ``E2E_SKIP_LIFECYCLE=1`` to
 * force-skip even when docker is present (e.g. in CI workers
 * without docker socket access).
 */

function resolveAlpineDigest() {
  if (process.env.E2E_SKIP_LIFECYCLE === '1') {
    return { ok: false, reason: 'E2E_SKIP_LIFECYCLE=1 — lifecycle suite skipped' }
  }
  try {
    execSync('docker pull -q alpine:3.19', {
      stdio: 'pipe',
      timeout: 60_000,
    })
  } catch (e) {
    return {
      ok: false,
      reason: `docker pull alpine:3.19 failed: ${e.message?.slice(0, 200) || 'unknown'}`,
    }
  }
  try {
    const out = execSync(
      'docker inspect --format="{{index .RepoDigests 0}}" alpine:3.19',
      { stdio: 'pipe' }
    )
      .toString()
      .trim()
    const at = out.indexOf('@')
    if (at < 0) return { ok: false, reason: `unexpected RepoDigests format: ${out}` }
    const digest = out.slice(at + 1)
    if (!digest.startsWith('sha256:')) {
      return { ok: false, reason: `digest missing sha256 prefix: ${digest}` }
    }
    return { ok: true, digest }
  } catch (e) {
    return {
      ok: false,
      reason: `docker inspect failed: ${e.message?.slice(0, 200) || 'unknown'}`,
    }
  }
}

const DIGEST = resolveAlpineDigest()

async function seedLaunchableChallenge(api, slug) {
  if (!DIGEST.ok) throw new Error('digest not resolved; suite should have skipped')
  const token = await api.adminToken()
  await api.createChallenge(token, {
    slug,
    title: `E2E Lifecycle ${slug}`,
    description: 'Real docker launch for the InstancePanel lifecycle suite.',
    category: 'web',
    difficulty: 1,
    points: 100,
    team: 'red',
    flag: 'CTF{REDACTED}',
    docker_image: 'alpine:3.19',
    docker_port: 8080,
    docker_config: { digest: DIGEST.digest, profile: 'default-strict' },
  })
  await api.releaseChallenge(token, slug)
  return slug
}

test.describe('Instance lifecycle (full launch → STOP → RESET)', () => {
  test.skip(!DIGEST.ok, () => DIGEST.reason || 'docker not available')

  test('launch then STOP returns to LAUNCH button', async ({
    authedUser, api,
  }) => {
    const slug = `e2e-lifecycle-stop-${Date.now().toString(36)}`
    await seedLaunchableChallenge(api, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    await page.locator(`text="E2E Lifecycle ${slug}"`).first().click()

    // LAUNCH.
    await page.locator('button:has-text("LAUNCH CHALLENGE")').first().click()

    // Panel renders, port chip shows a number.
    const panel = page.locator('[data-testid="instance-panel"]')
    await expect(panel).toBeVisible({ timeout: 30_000 })
    const portChip = page.locator('[data-testid="instance-port"]')
    await expect(portChip).toBeVisible()
    const launchedPort = (await portChip.textContent())?.trim()
    expect(launchedPort).toMatch(/^\d+$/)

    // STOP.
    await page.locator('[data-testid="instance-stop"]').click()

    // Panel disappears, LAUNCH button is back.
    await expect(panel).toBeHidden({ timeout: 15_000 })
    await expect(
      page.locator('button:has-text("LAUNCH CHALLENGE")')
    ).toBeVisible()

    // Stop toast surfaced.
    await expect(
      page.locator('[data-testid="toast-success"]').first()
    ).toContainText(/stopped/i, { timeout: 5_000 })
  })

  test('launch then RESET swaps the running container', async ({
    authedUser, api,
  }) => {
    const slug = `e2e-lifecycle-reset-${Date.now().toString(36)}`
    await seedLaunchableChallenge(api, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    await page.locator(`text="E2E Lifecycle ${slug}"`).first().click()

    await page.locator('button:has-text("LAUNCH CHALLENGE")').first().click()
    const panel = page.locator('[data-testid="instance-panel"]')
    await expect(panel).toBeVisible({ timeout: 30_000 })
    const portChip = page.locator('[data-testid="instance-port"]')
    const initialPort = (await portChip.textContent())?.trim()
    expect(initialPort).toMatch(/^\d+$/)

    // RESET.
    await page.locator('[data-testid="instance-reset"]').click()

    // The reset toast carries the new port; assert it appears.
    await expect(
      page.locator('[data-testid="toast-success"]').first()
    ).toContainText(/reset.*port/i, { timeout: 30_000 })

    // Panel still visible (it swapped to the new instance via the
    // store's byChallenge map). Verify the port chip updated.
    await expect(panel).toBeVisible()
    await expect(async () => {
      const next = (await portChip.textContent())?.trim()
      expect(next).toMatch(/^\d+$/)
      expect(next).not.toBe(initialPort)
    }).toPass({ timeout: 10_000 })

    // Cleanup: STOP so we don't leak an instance into subsequent
    // tests (workers=1; sequential run).
    await page.locator('[data-testid="instance-stop"]').click()
    await expect(panel).toBeHidden({ timeout: 15_000 })
  })

  test('countdown chip shows expiry remaining', async ({
    authedUser, api,
  }) => {
    const slug = `e2e-lifecycle-countdown-${Date.now().toString(36)}`
    await seedLaunchableChallenge(api, slug)

    const { page } = authedUser
    await page.goto(`/challenges?slug=${slug}`)
    await page.locator(`text="E2E Lifecycle ${slug}"`).first().click()
    await page.locator('button:has-text("LAUNCH CHALLENGE")').first().click()

    const expiry = page.locator('[data-testid="instance-expiry"]')
    await expect(expiry).toBeVisible({ timeout: 30_000 })
    // Format is one of "Xh Ym" / "Xm Ys" / "Xs". Match any.
    await expect(expiry).toHaveText(/\d+(h|m|s)/, { timeout: 5_000 })

    await page.locator('[data-testid="instance-stop"]').click()
    await expect(
      page.locator('[data-testid="instance-panel"]')
    ).toBeHidden({ timeout: 15_000 })
  })
})
