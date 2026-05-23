# Red-team launch notes — seige-range full audit

## Target
- A pre-existing seige-range stack is already running on the audit host:
  - `seige-range-api-1` — backend (uvicorn :8000)
  - `seige-range-nginx-1` — Nginx front (host :3000)
  - `seige-range-orchestrator-1` — DinD challenge orchestrator (host :10000-10049, :11000-11199)
  - Plus Postgres / Redis service containers.
- Confirmed reachable: `GET http://localhost:3000/healthz` → 200.
- Confirmed reachable from inside the API container: `GET http://localhost:8000/openapi.json` → 200 with full route list.
- **Note:** the host-side Nginx (`:3000`) returns 404 for `/api/v1/*` against my probes (it appears not to proxy that path in the running config — possibly a stale dev config). PoCs therefore target the **API container directly** via `docker exec seige-range-api-1 curl ...`. This is the same uvicorn process the real users would hit; the nginx-layer issue is a separate observation (see `audit-report.md` out-of-scope notes).
- All probes are read-only or create disposable test users on the running dev stack. **No teardown** — the stack was already up; leaving it as found.

## Reachability checks
- `curl http://localhost:3000/healthz` → `200`
- `curl http://localhost:3000/openapi.json` → 200, but body is the SPA's `index.html` (so nginx is rewriting `/openapi.json` to the SPA's catch-all; OpenAPI is **only** reachable inside the container in this deployment).
- `docker exec seige-range-api-1 curl http://localhost:8000/openapi.json` → 200 JSON, full route list captured.

## Critical live-target confirmation (independent of PoCs below)
`content-redacted-policy` header (not `content-security-policy`) is present on every response from the running API. Verified via:
```
docker exec seige-range-api-1 curl -s -i -X POST http://localhost:8000/api/v1/auth/login \
   -H 'Content-Type: application/json' -d '{"email":"a@a.com","password":"pw"}'
```
This is the AS-1 / CR-1 finding observed in production behaviour.

## Constraints
- Local-only.
- No production data — the running stack is the dev fixture.
- No third-party calls.
- Will create disposable users only; no cleanup needed (the stack is dev).

## Teardown
- Not applicable: the stack was running before the audit started and remains running. No new containers, volumes, or networks were created.
