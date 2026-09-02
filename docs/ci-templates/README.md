# CI templates (reference)

These four workflow files describe the canonical CI shape for the
heavier pipelines. The live pipeline is `.github/workflows/ci.yml`;
these are kept as reference for forks and derivatives that want the
full docker-stack test matrix.

| File | What it runs |
|---|---|
| `backend-tests.yml` | pytest suite (testcontainer Postgres + Redis), spec package tests, harness smoke. Triggers on `backend/**` or `packages/castra-spec/**`. |
| `browser-tests.yml` | Full docker-compose stack + Playwright chromium suite. Triggers on `frontend/**`, v1 routers, auth router, challenges router, compose files. |
| `challenge-tests.yml` | `app.tools.test_harness` against `examples/challenges/`. Triggers on `examples/challenges/**` or `backend/app/services/test_harness/**`. |
| `docker-images.yml` | buildx + GHA cache for `siege-egress-sidecar:latest` and `siege-egress-proxy`. Triggers on `docker/**` or `docker-compose.yml`. |

## Running the same checks locally

```bash
make test                                       # backend-tests + spec-tests
cd frontend && npx playwright test              # browser-tests (needs make dev up)
make test-challenges                            # challenge-tests
docker compose build egress-sidecar egress-proxy  # docker-images
```
