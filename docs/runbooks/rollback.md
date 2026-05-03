# Runbook — Rollback a deploy

## When to use

The new release is broken in production:

- API returning 5xx in `/healthz` or `/readyz`
- Migration applied unexpected schema changes
- Audit ledger reports tampering (`python -m app.tools.audit_verify` exits non-zero)
- Critical security issue in the just-shipped commit

## Decision tree

| Symptom | Action |
|---|---|
| App container OOM / crash-looping | Roll back container only (skip DB rollback). |
| Pre-existing alembic head mismatches code | Roll back app and apply alembic `downgrade -1`. |
| Schema corruption / data loss | Stop everything, restore from backup (`db-restore.md`). |

## Rollback (container only — most cases)

1. Identify the previous-known-good image tag:

   ```bash
   docker compose images api
   git log --oneline backend/ | head -5  # find the previous commit
   ```

2. Check out the previous commit:

   ```bash
   git checkout <previous-sha>
   ```

3. Rebuild and redeploy:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build api dashboard
   ```

4. Verify:

   ```bash
   curl -fsS https://localhost/healthz
   curl -fsS https://localhost/readyz
   ```

5. If healthy, capture the running image digest for next time:

   ```bash
   docker compose images api
   ```

6. Tag the rollback in your tracker (Linear/Jira/etc.) so the broken
   commit doesn't get re-deployed.

## Rollback (with alembic downgrade)

Only do this if the broken release applied a migration. Check the
migration history first:

```bash
docker compose exec api alembic history --verbose | head -20
docker compose exec api alembic current
```

If the head is the just-shipped migration:

1. **Take a logical backup before downgrading.** Migrations may
   irreversibly alter data:

   ```bash
   bash scripts/backup.sh
   # Verify the backup file:
   ls -la backups/
   ```

2. Downgrade one step:

   ```bash
   docker compose exec api alembic downgrade -1
   ```

3. Roll the app back as in the container-only flow above.

4. Verify schema matches expectations:

   ```bash
   docker compose exec db psql -U siege siege_range -c '\dt'
   ```

## Rollback to a known-good backup

If both code and data are bad — see `db-restore.md`.

## After action

- File a bug with the broken commit SHA, the symptoms, and the
  `audit_ledger` events around the failure.
- Hold a mini-postmortem within 48 hours. Update this runbook if a
  new symptom-class needs a new branch.

## Estimated time

Container-only: **5 minutes**. With alembic downgrade: **15 minutes**.
With db-restore: see `db-restore.md` (target: under 30 minutes).
