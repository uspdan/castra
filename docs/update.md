# Updating a running deployment

What an operator runs when a new release lands. Migrations are append-only
and run automatically before the API serves traffic, so the happy path is
short. Take a backup first.

## Roll forward

```bash
# 1. Back up the database (safety net for the migration step).
make backup

# 2. Pull the new code.
git fetch origin && git checkout <tag-or-main> && git pull

# 3. Rebuild and restart. Migrations run automatically on API start.
make prod            # or `make dev` locally

# 4. Rebuild challenge images if any changed.
bash scripts/build_challenge_images.sh

# 5. Smoke-test.
make health          # /health + /readyz
```

If challenge manifests changed, re-seed:
```bash
make seed
```

## Migrations

- Migrations live in `backend/migrations/versions/` and are timestamp/
  revision ordered. They are **append-only** — never edit an applied one.
- They run as part of API startup (`alembic upgrade head`); no manual step
  is required in the normal case.
- To inspect pending state manually:
  ```bash
  docker compose exec api alembic current
  docker compose exec api alembic history --indicate-current
  ```

## Rollback

A deploy is reversible as long as the new release contained no
destructive (down-only) migration.

```bash
# 1. Check out the previous release.
git checkout <previous-tag>

# 2. If the new release added migrations, step the schema back first.
docker compose exec api alembic downgrade -1     # repeat per new revision

# 3. Rebuild and restart.
make prod

# 4. If schema rollback isn't possible (a destructive migration), restore
#    the pre-upgrade backup instead:
make restore FILE=backups/siege-backup-<DATE>.tar.gz
```

Destructive schema changes are staged over two releases (deprecate in N,
remove in N+1) specifically so a single-release rollback stays safe. If
you must restore from backup, do it before letting traffic back in.

## Verify after any change

```bash
make health
curl https://<domain>/readyz     # 200 == ready to serve
```
