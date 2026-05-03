# Runbook — Rotate platform secrets

## When to use

- Secret leaked / suspected leaked (commit, screenshot, ex-employee)
- Quarterly hygiene rotation
- Pre-prod handover from staging

## Secrets covered

| Secret | What it protects | Rotation impact |
|---|---|---|
| `SECRET_KEY` | JWT signing | All sessions invalidated; users must log in again |
| `ADMIN_PASSWORD` | Bootstrap admin login | Admin must use new password |
| `POSTGRES_PASSWORD` | DB connection | API restart required; DB volume retained |
| `WEBHOOK_SUBSCRIPTION.secret` | Per-subscription HMAC | Per-receiver re-config; not platform-wide |

This runbook covers the first three. Webhook secrets rotate via
DELETE+POST on `/api/v1/webhooks/{id}` (operator-driven, not a
platform-wide event).

## Pre-flight

1. Notify operators / users of a planned ~2-minute API window.
2. Take a backup (`bash scripts/backup.sh`).

## Rotate `SECRET_KEY`

This is the most disruptive — every JWT in flight becomes invalid the
moment the API restarts with the new key.

1. Generate a new key (32+ chars, high entropy):

   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. Update `.env`:

   ```bash
   sed -i.bak "s/^SECRET_KEY=.*/SECRET_KEY=<new-value>/" .env
   ```

3. Restart the API:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
       restart api
   ```

4. Verify boot:

   ```bash
   docker compose logs -f api | head -20
   ```

5. Notify users they need to log in again.

**Note**: Refresh tokens issued with the old key are now invalid.
Users see one 401 → automatic logout via the axios interceptor in
`frontend/src/api/client.js`.

## Rotate `ADMIN_PASSWORD`

This is the password used by `_create_admin_user` on first boot. It's
also the password the bootstrap admin logs in with.

1. Update the password directly via the running app (preferred —
   doesn't require restart):

   ```bash
   docker compose exec api python <<'PY'
   import asyncio
   from sqlalchemy import select
   from app.database import async_session
   from app.models import User
   from app.services.auth import hash_password

   async def main():
       async with async_session() as db:
           result = await db.execute(
               select(User).where(User.username == 'admin')
           )
           admin = result.scalar_one()
           admin.hashed_password = hash_password('<NEW-PASSWORD>')
           await db.commit()
   asyncio.run(main())
   PY
   ```

2. Update `.env` for future cold starts:

   ```bash
   sed -i.bak "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=<NEW-PASSWORD>/" .env
   ```

3. Verify the new password works:

   ```bash
   curl -X POST https://localhost/api/auth/login \
       -H "Content-Type: application/json" \
       -d '{"email":"admin@siege.local","password":"<NEW>"}'
   ```

## Rotate `POSTGRES_PASSWORD`

The DB password is set by Postgres on first volume init and persists
across restarts. To rotate without losing data:

1. Connect to the running DB:

   ```bash
   docker compose exec db psql -U siege siege_range
   ```

2. Change the password:

   ```sql
   ALTER USER siege WITH PASSWORD '<new-password>';
   ```

3. Update `.env`:

   ```bash
   sed -i.bak "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=<new>/" .env
   ```

4. Restart the API so it picks up the new connection string:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
       restart api
   ```

5. Verify the API can connect:

   ```bash
   curl -fsS https://localhost/readyz
   ```

## After action

- Delete the `.env.bak` files created by `sed`:

  ```bash
  rm .env.bak
  ```

- Audit-ledger entries are NOT auto-emitted for secret rotation.
  Log the rotation manually in your tracker (date, who, which
  secrets).
- Schedule the next rotation (calendar reminder for 90 days).

## Estimated time

`SECRET_KEY`: **5 minutes** including user re-login.
`ADMIN_PASSWORD`: **2 minutes**.
`POSTGRES_PASSWORD`: **5 minutes** (one API restart).
