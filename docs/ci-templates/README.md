# CI templates (deactivated)

These four workflow files used to live in `.github/workflows/` but
are parked here while GitHub Actions is disabled on this account.
They aren't deleted because the test pipelines they describe are
the canonical CI shape — if Actions is ever turned back on, copy
them back into `.github/workflows/` and they'll work as-is.

| File | What it runs |
|---|---|
| `backend-tests.yml` | pytest suite (testcontainer Postgres + Redis), spec package tests, harness smoke. Triggers on `backend/**` or `packages/bluerange-spec/**`. |
| `browser-tests.yml` | Full docker-compose stack + Playwright chromium suite. Triggers on `frontend/**`, v1 routers, auth router, challenges router, compose files. |
| `challenge-tests.yml` | `app.tools.test_harness` against `examples/challenges/`. Triggers on `examples/challenges/**` or `backend/app/services/test_harness/**`. |
| `docker-images.yml` | buildx + GHA cache for `siege-egress-sidecar:latest` and `siege-egress-proxy`. Triggers on `docker/**` or `docker-compose.yml`. |

## Verification today

While Actions stays off, run the same checks locally:

```bash
make test                                       # backend-tests + spec-tests
cd frontend && npx playwright test              # browser-tests (needs make dev up)
make test-challenges                            # challenge-tests
docker compose build egress-sidecar egress-proxy  # docker-images
```

The May-17 scheduled remote agent (claude.ai routine
`trig_01MkVrRmP9242enav9aNWuqW`) also exercises the docker-stack
path against a real docker host, including the lifecycle
Playwright suite.
