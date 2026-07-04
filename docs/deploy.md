# Deploying seige-range

Three flavours: local dev, staging, and an internet-exposed production
deploy. Every secret is supplied via `.env` (gitignored); a documented
placeholder for each lives in `.env.example`.

## Prerequisites

- Docker 24+ with Compose v2.
- A `.env` file. Start from the template:
  ```bash
  cp .env.example .env
  ```
  The API **fails fast** on boot if `SECRET_KEY` or `ADMIN_PASSWORD` are
  missing or set to a known placeholder. Generate real values:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"   # SECRET_KEY
  ```
  Pick a strong `ADMIN_PASSWORD` (≥12 chars, not an obvious placeholder).

## Local development

```bash
make dev          # docker-compose.yml + docker-compose.dev.yml, --build
make seed         # load examples/challenges/* into the DB
```
Dashboard: `http://localhost:${SIEGE_PORT:-3000}`. Live reload and relaxed
timeouts come from the dev override. Tear down with `make down`.

## Staging

```bash
make prod         # docker-compose.yml + docker-compose.prod.yml
```
Staging uses the production image build and overrides but points at
staging DNS / secrets. Run the health check after it settles:
```bash
make health
```

## Production (internet-exposed)

1. **DNS + TLS.** Point your domain at the host. Terminate TLS at nginx
   (mount your cert/key into `nginx/certs/`, which is gitignored) or at an
   upstream load balancer. Set `ALLOWED_ORIGINS` and `FRONTEND_URL` to the
   public origin.
2. **Secrets.** Populate `.env` with real values for at least:
   `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `POSTGRES_PASSWORD`,
   and — if email is used — the `SMTP_*` / `MAIL_FROM` set. Consider
   `REQUIRE_EMAIL_VERIFIED=true`.
3. **Bring it up.**
   ```bash
   make prod
   ```
   Migrations run automatically before the API accepts traffic.
4. **Observability (optional).** Set `OTEL_EXPORTER_OTLP_ENDPOINT` and
   `OTEL_SERVICE_NAME` to ship traces to your collector.
5. **Backups.** Nightly `pg_dump` runs in-process; tune `BACKUP_DIR` and
   `BACKUP_RETENTION_DAYS`. Verify with `make backup`.
6. **Verify.**
   ```bash
   make health          # /health + /readyz
   curl https://<domain>/readyz
   ```

## Environment reference

Every configurable value is documented in `.env.example`. Precedence is
env vars → `.env` → in-code defaults; production must not rely on
defaults for any secret.

## Rolling out a new version

See [`update.md`](update.md).
