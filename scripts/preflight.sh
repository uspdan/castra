#!/usr/bin/env bash
# scripts/preflight.sh — validate a deployment before `make prod`.
#
# Catches the misconfigurations that otherwise only surface as a
# crash-looping api container or an nginx that can't bind :443:
#   * missing / incomplete .env (placeholder or empty secrets)
#   * missing TLS material expected by docker-compose.prod.yml
#   * missing tls-redirect.conf (HTTP would keep serving plaintext)
#   * production SMTP / origin requirements from backend/app/config.py
#
# Usage: ./scripts/preflight.sh        (run from the repo root)
#        make preflight

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"
CERT_DIR="${PROJECT_ROOT}/nginx/certs"

failures=0

fail() {
    echo "[FAIL] $1" >&2
    failures=$((failures + 1))
}

warn() {
    echo "[WARN] $1" >&2
}

ok() {
    echo "[ ok ] $1"
}

# ── .env presence ────────────────────────────────────────────────────
if [ ! -f "${ENV_FILE}" ]; then
    fail ".env not found — copy .env.example and fill in the secrets"
    echo
    echo "preflight: ${failures} blocking problem(s)." >&2
    exit 1
fi
ok ".env present"

# Read a key's value from .env without exporting anything.
env_get() {
    sed -n "s/^$1=//p" "${ENV_FILE}" | tail -1
}

APP_ENV="$(env_get APP_ENV)"
APP_ENV="${APP_ENV:-development}"
ok "APP_ENV=${APP_ENV}"

# ── secrets ──────────────────────────────────────────────────────────
SECRET_KEY="$(env_get SECRET_KEY)"
if [ -z "${SECRET_KEY}" ]; then
    fail "SECRET_KEY is empty (generate: python3 -c 'import secrets; print(secrets.token_hex(32))')"
elif [ "${#SECRET_KEY}" -lt 32 ]; then
    fail "SECRET_KEY is shorter than 32 characters"
elif printf '%s' "${SECRET_KEY}" | grep -qi 'change-me\|changeme\|example\|placeholder'; then
    fail "SECRET_KEY looks like a placeholder"
else
    ok "SECRET_KEY set (${#SECRET_KEY} chars)"
fi

ADMIN_PASSWORD="$(env_get ADMIN_PASSWORD)"
if [ -z "${ADMIN_PASSWORD}" ]; then
    fail "ADMIN_PASSWORD is empty"
elif [ "${#ADMIN_PASSWORD}" -lt 12 ]; then
    fail "ADMIN_PASSWORD is shorter than 12 characters"
elif [ "${ADMIN_PASSWORD}" = 'Admin123!@#' ]; then
    fail "ADMIN_PASSWORD is the documented placeholder"
else
    ok "ADMIN_PASSWORD set"
fi

POSTGRES_PASSWORD="$(env_get POSTGRES_PASSWORD)"
if [ "${APP_ENV}" = "production" ] && [ "${POSTGRES_PASSWORD:-siege_secret}" = "siege_secret" ]; then
    fail "POSTGRES_PASSWORD is the default 'siege_secret' in production"
fi

# ── production-only requirements (mirror backend/app/config.py) ─────
if [ "${APP_ENV}" = "production" ]; then
    for key in ALLOWED_ORIGINS SMTP_HOST MAIL_FROM FRONTEND_URL; do
        if [ -z "$(env_get "${key}")" ]; then
            fail "${key} must be set when APP_ENV=production (api refuses to boot without it)"
        else
            ok "${key} set"
        fi
    done

    # ── TLS material expected by docker-compose.prod.yml ────────────
    if [ ! -f "${CERT_DIR}/server-bundle.crt" ] || [ ! -f "${CERT_DIR}/server.key" ]; then
        fail "TLS certs missing at nginx/certs/ — run scripts/generate_certs.sh or drop in real certs"
    else
        ok "TLS certs present"
        if command -v openssl >/dev/null 2>&1; then
            if ! openssl x509 -checkend 0 -noout -in "${CERT_DIR}/server-bundle.crt" >/dev/null 2>&1; then
                fail "nginx/certs/server-bundle.crt is expired"
            elif ! openssl x509 -checkend 2592000 -noout -in "${CERT_DIR}/server-bundle.crt" >/dev/null 2>&1; then
                warn "TLS cert expires within 30 days"
            fi
        fi
    fi

    if [ ! -f "${PROJECT_ROOT}/nginx/conf.d/tls-redirect.conf" ]; then
        fail "nginx/conf.d/tls-redirect.conf absent — port 80 will keep serving plaintext (cp the .example file)"
    else
        ok "HTTP→HTTPS redirect enabled"
    fi

    if [ ! -f "${PROJECT_ROOT}/docker-compose.digests.yml" ]; then
        warn "docker-compose.digests.yml absent — infra images will float on tags (run scripts/refresh-image-digests.sh)"
    fi
fi

# ── workstation password (optional feature, required if used) ───────
if [ -z "$(env_get SIEGE_WORKSTATION_PASSWORD)" ]; then
    warn "SIEGE_WORKSTATION_PASSWORD unset — 'make workstation-up' will refuse to start"
fi

echo
if [ "${failures}" -gt 0 ]; then
    echo "preflight: ${failures} blocking problem(s)." >&2
    exit 1
fi
echo "preflight: all checks passed."
