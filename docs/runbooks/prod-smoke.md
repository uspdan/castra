# Runbook — Production smoke test

## When to use

- After a fresh `make prod` deploy on a new host.
- After a major version bump or migration.
- After an infrastructure change (TLS cert rotation, network
  rewire, secrets rotation, docker engine upgrade).
- Quarterly hygiene check on a long-running deployment.

## Estimated time

~20 minutes for the full matrix; ~5 minutes for the smoke-only
subset (steps 1–5).

## Pre-flight

Set the host you're targeting:

```bash
export SIEGE_HOST=siege.example.com   # public DNS or IP
```

Confirm prerequisites:

```bash
ssh "$SIEGE_HOST" 'docker --version && docker compose version'
ssh "$SIEGE_HOST" 'ls /etc/letsencrypt/live/$SIEGE_HOST/fullchain.pem'  # or your cert path
ssh "$SIEGE_HOST" 'cat /opt/siege-range/.env | grep -E "^(SECRET_KEY|ADMIN_PASSWORD|POSTGRES_PASSWORD|MAIL_FROM|SMTP_HOST)" | wc -l'
# expect 5+ lines (no empty values)
```

## Smoke matrix

### 1. Liveness + readiness

```bash
curl -sSf "https://$SIEGE_HOST/health"           # → {"status":"ok","version":"…"}
curl -sSf "https://$SIEGE_HOST/healthz"          # → {"status":"ok"}
curl -sSf "https://$SIEGE_HOST/readyz" | jq      # → ok=true on every probe
```

If `readyz` reports a probe failure: check the corresponding
component (`docker compose -f docker-compose.prod.yml logs db|redis|docker-proxy`).

### 2. TLS + security headers

```bash
curl -sIv "https://$SIEGE_HOST/" 2>&1 | grep -iE \
  "(strict-transport-security|x-content-type-options|x-frame-options|content-security-policy)"
```

Expected: HSTS with `max-age=31536000; includeSubDomains; preload`,
nosniff, DENY, and a CSP. Cert chain should validate against the
default trust store (`curl` should NOT need `-k`).

### 3. v1 auth round-trip

```bash
ADMIN_EMAIL=admin@siege.local        # whatever ADMIN_EMAIL is set to
ADMIN_PASSWORD='…'                   # value from .env

# Login.
TOKEN=$(curl -sSf -X POST "https://$SIEGE_HOST/api/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
  | jq -r .access_token)
test -n "$TOKEN" || { echo "login failed"; exit 1; }

# Whoami.
curl -sSf "https://$SIEGE_HOST/api/api/v1/me" \
  -H "Authorization: Bearer $TOKEN" | jq .username
```

(The `/api/api/v1` double-prefix is intentional — nginx strips the
outer `/api/` before proxying; see `nginx/nginx.conf`.)

### 4. Audit ledger integrity

```bash
ssh "$SIEGE_HOST" 'docker compose -f /opt/siege-range/docker-compose.prod.yml \
  exec -T api python -m app.tools.audit_verify'
# Expected exit code 0 — chain intact.
```

If non-zero: STOP. Tamper detection runbook (TODO) or investigate
out-of-band. Do NOT continue the smoke.

### 5. Egress allowlist render + tinyproxy reload

```bash
ssh "$SIEGE_HOST" 'docker compose -f /opt/siege-range/docker-compose.prod.yml \
  exec -T api python -m app.tools.render_egress_allowlist --json'
# Expected: { target, instance_count, fqdn_count, rule_count }.

ssh "$SIEGE_HOST" 'docker logs siege-egress-proxy --tail 50 | grep -i hup'
# After the render call, expect at least one SIGHUP / reload entry.
```

### 6. Instance launch + lifecycle (optional, requires sample challenge)

```bash
# Pick a released challenge slug; admin can list:
curl -sSf "https://$SIEGE_HOST/api/api/v1/challenges?per_page=5" \
  -H "Authorization: Bearer $TOKEN" | jq '.items[].slug'

SLUG=…  # paste one

# Launch.
LAUNCH=$(curl -sSf -X POST "https://$SIEGE_HOST/api/instances/$SLUG/launch" \
  -H "Authorization: Bearer $TOKEN")
INSTANCE_ID=$(echo "$LAUNCH" | jq .id)
PORT=$(echo "$LAUNCH" | jq .port)
echo "instance $INSTANCE_ID on port $PORT"

# Stop.
curl -sSf -X DELETE "https://$SIEGE_HOST/api/instances/$INSTANCE_ID" \
  -H "Authorization: Bearer $TOKEN" | jq .detail
```

### 7. Email pipeline (Sprint 6+)

If SMTP is configured (`SMTP_HOST` set in `.env`):

```bash
TEST_EMAIL=ops-test@yourcompany.invalid
curl -sSf -X POST "https://$SIEGE_HOST/api/api/v1/auth/forgot-password" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$TEST_EMAIL\"}"
# Expect HTTP 202 with a generic message.

# Tail the email log (whether SMTP delivered or stderr-fallback):
ssh "$SIEGE_HOST" 'docker compose -f /opt/siege-range/docker-compose.prod.yml \
  logs api --tail 30 | grep -i email'
```

### 8. Frontend smoke

```bash
curl -sSf "https://$SIEGE_HOST/" | grep -i siege
# Expect HTML containing the page shell.

curl -sSI "https://$SIEGE_HOST/assets/" | head -3
# Static asset path served.
```

### 9. WebSocket connectivity (optional)

```bash
# Requires websocat or similar.
echo '{"type":"ping"}' | websocat -n1 \
  "wss://$SIEGE_HOST/ws/?token=$TOKEN"
# Expect a JSON response (pong / ack).
```

## Verification

All steps return successfully and audit-verify exits 0. Capture
the output of each step into a smoke-log file:

```bash
( for step in 1 2 3 4 5 8; do echo "## step $step ##"; done ) \
  > /tmp/prod-smoke-$(date +%Y%m%d).log
```

Save into `docs/runbooks/smoke-logs/` for the deploy ticket.

## After-action

- If any step failed, file an issue with the step number, exact
  command output, and the host's docker logs for the affected
  service. Page the on-call engineer if the failure is visible
  to users.
- Update `CHANGELOG.md` with the deploy date + smoke result.
- Schedule the next quarterly smoke via `/schedule` if it isn't
  already on a recurring routine.
