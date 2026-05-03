#!/usr/bin/env bash
# Sprint 1 — alembic-on-boot entrypoint.
#
# Production / staging containers start through this script so the
# schema is migration-driven rather than ``Base.metadata.create_all``-
# driven (the latter cannot DROP, ALTER, or apply per-migration
# triggers; the audit-ledger immutability trigger from migration 002,
# the slice-8 drop_audit_logs migration, etc. are all alembic-only).
#
# The container app process inherits ``DB_MIGRATIONS_MANAGED_EXTERNALLY=1``
# so ``app.database.init_db`` skips its create_all fallback — alembic
# is the single source of truth in this codepath.
#
# Failure mode: if ``alembic upgrade head`` fails, the container exits
# non-zero before uvicorn starts. The orchestrator's healthcheck-driven
# dependency graph keeps the rest of the stack from coming up.

set -euo pipefail

cd /app

# Wait briefly for Postgres before alembic issues its first DDL — keeps
# the api container from racing the database during a cold compose-up.
# We do a plain TCP probe (no driver dep) since we just need to know
# the port is accepting connections; alembic surfaces auth / DB-name
# errors on the next step with a clear message.
python <<'PY'
import os
import socket
import sys
import time
import urllib.parse

raw = os.environ.get("DATABASE_URL", "")
if not raw:
    print("DATABASE_URL not set; skipping wait-for-db", file=sys.stderr)
    sys.exit(0)

parsed = urllib.parse.urlparse(raw.replace("+asyncpg", ""))
host = parsed.hostname or "localhost"
port = parsed.port or 5432

deadline = time.time() + 60
last_err = None
while time.time() < deadline:
    try:
        with socket.create_connection((host, port), timeout=3):
            sys.exit(0)
    except OSError as exc:
        last_err = exc
        time.sleep(2)

print(f"postgres did not become ready in 60s: {last_err}", file=sys.stderr)
sys.exit(1)
PY

echo "[entrypoint] running alembic upgrade head"
alembic upgrade head

export DB_MIGRATIONS_MANAGED_EXTERNALLY=1
echo "[entrypoint] migrations applied; exec '$*'"

# Honour whatever CMD the image / compose set; defaults to uvicorn
# via the Dockerfile but operators can override (``docker run …
# bash`` for an interactive shell).
exec "$@"
