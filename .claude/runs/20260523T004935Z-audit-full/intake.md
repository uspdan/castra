# Intake — seige-range full-project audit

- Mode: AUDIT (project-scoped, read-only)
- Run id: 20260523T004935Z-audit-full
- Project: /data/projects/seige-range
- Commit: 117eb3e1c919f71ef7bbd2efdcaaa6a80559a42f
- Branch: main

## Scope
- Whole working tree.
- **In-scope (platform code, held to CLAUDE.md standards):**
  - `backend/` — FastAPI + SQLAlchemy async backend.
  - `frontend/` — React + Vite SPA.
  - `infra/`, `nginx/`, `docker/`, `docker-compose*.yml`, `Dockerfile`s.
  - `scripts/`, `Makefile`, `.github/workflows/`.
  - `secrets/` directory layout (gitignored content is out of scope, but `.gitignore` / templates are in scope).
  - `packages/` (shared libs, if any).
  - `docs/`, top-level `*.md` (context only — flagged for accuracy/secret-leak, not engineering review).
- **Out-of-scope by design:**
  - `challenges/` — intentionally-vulnerable CTF training material. Vulnerabilities here are *features*, not findings. Flag only if they leak the platform-level secrets/flags or escape the challenge sandbox.
  - `examples/` — likewise, illustrative vulnerable code for training.
  - `frontend/node_modules/`, `frontend/dist/`, `frontend/test-results/`, `frontend/playwright-report/` — gitignored build/test output.
  - `__pycache__/`, `.venv*/`, `dist/`, `build/` — gitignored build output.
  - `dind_data/`, `backups/`, `nginx/certs/` — gitignored runtime state.
  - `secrets/flags.json`, `secrets/answers/*` — gitignored runtime secrets; treat their *handling* as in-scope but not their contents.

## Languages and frameworks
- Backend: Python (FastAPI, SQLAlchemy async, Alembic), pyproject.toml + requirements.txt.
- Frontend: JavaScript/JSX (React, Vite, Playwright).
- Infra: Docker, docker-compose (dev/prod), Nginx reverse proxy, Docker-in-Docker for challenge orchestration, ttyd for browser shells.
- CI: GitHub Actions (backend-tests unit only, frontend-build, trufflehog secret-scan, flag-leak guard).

## Sensitivity hints (regulated-data exposure)
- **Authentication / credentials**: YES — user auth, password reset flow, session/JWT handling. Compliance review required.
- **Audit ledger**: YES — submission events keyed to authenticated identity.
- **PII**: PARTIAL — user accounts (email, hashed password), submission history. No payment, no health data observed.
- **Payment**: NO.
- **Health (HIPAA)**: NO.
- **Children's data (COPPA)**: UNKNOWN — CTF audience could include under-18s; flag for compliance.

Compliance phase: **REQUIRED** (auth, PII, audit ledger present).

## Context (not in scope, but informs audit)
- Repo is public (`uspdan/seige-range`).
- Recently: SHA-256 flag sealing, per-question answer sealing, cheat detector, git-history rewrite to scrub `CTF{...}` literals, branch protection on main, four required CI checks.
- Integration tests not yet wired into CI (testcontainers config pending).
- 62 CTF challenges intentionally vulnerable.

## Decisions
- Mode set to AUDIT by user (explicit).
- All 9 phases will run, including red-team, blue-team, compliance, codex.
- No clarifying question to user — scope was given concretely.
- Per user directive: do not pause for clarification; make reasonable calls and continue.

## Exclusion globs (passed to specialists)
- `challenges/**` (out-of-scope: training material)
- `examples/**` (out-of-scope: training material)
- `frontend/node_modules/**`
- `frontend/dist/**`
- `frontend/test-results/**`, `frontend/playwright-report/**`, `frontend/.playwright/**`
- `**/__pycache__/**`, `**/.venv*/**`, `**/dist/**`, `**/build/**`
- `dind_data/**`, `backups/**`, `nginx/certs/**`
- `siege_backend.egg-info/**`
- `*.log` (per .gitignore note: challenge log corpora *are* source, but they live under `challenges/` which is already excluded)
