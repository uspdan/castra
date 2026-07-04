# Connecting to seige-range

How to reach every layer of a running stack — as a hunter, an author, or
an operator. All credentials are referenced by environment variable
(`${VAR}`); never paste real secrets into commands you share.

## Ports map

```
                        host
   ${SIEGE_PORT:-3000} ─▶ [nginx :80] ─┬─▶ dashboard SPA        (/)
                                        └─▶ api  (FastAPI :8000) (/api/*)
   challenge SSH ports  ─▶ per-instance containers (10000-10049 by default)
```

Everything else (db, redis, orchestrator/DinD, docker-proxy, egress-proxy)
is on internal Docker networks and is **not** published to the host.

## As a player / hunter

| Target | How |
|---|---|
| Dashboard UI | `http://<host>:${SIEGE_PORT:-3000}/` |
| API | same origin, under `/api/v1/*` |
| Live-shell challenge | launch from the UI; connect via the SSH port it prints, or in-browser ttyd at `/workstation/` |
| Offline runner | `scripts/seige start <slug>` then `scripts/seige connect <slug>` (see `docs/player-handbook.md`) |

## As an operator (host shell)

These use `docker compose exec`; no ports are exposed for them.

| Target | Command |
|---|---|
| API container shell | `docker compose exec api sh` |
| API liveness / readiness | `curl http://localhost:${SIEGE_PORT:-3000}/health` · `/readyz` |
| Postgres console | `docker compose exec db psql -U "${POSTGRES_USER}" "${POSTGRES_DB}"` |
| Redis console | `docker compose exec redis redis-cli` |
| DinD docker daemon | `docker compose exec orchestrator docker ps` |
| Metrics | `curl http://localhost:${SIEGE_PORT:-3000}/metrics` |
| Health script | `make health` (wraps `scripts/health_check.sh`) |

`${POSTGRES_USER}` / `${POSTGRES_DB}` come from your `.env`. The Postgres
password is never needed on the command line inside the container (peer
/ trust auth on the internal network); do not pass it on a shared shell.

## As an author

| Target | How |
|---|---|
| Load a challenge into a running stack | `make seed` (see `docs/author-new-challenge.md`) |
| Validate a manifest offline | `make test-challenges` |
| Build a challenge image | `bash scripts/build_challenge_images.sh <slug>` |

## Notes

- The API is only reachable through nginx on the published port; it does
  not listen on the host directly.
- `/health` and `/readyz` are unauthenticated but excluded from access
  logs. Everything under `/api/v1` requires a bearer token except the
  auth and health routes.
