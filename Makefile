.PHONY: dev prod down seed challenge-images test test-install test-challenges test-browser test-browser-install regen-schema render-egress-allowlist health backup restore build lint

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

prod:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

down:
	docker compose down -v

seed:
	python scripts/seed_challenges.py

challenge-images:
	bash scripts/build_challenge_images.sh

# Tests run on the host so testcontainers can spawn ephemeral Postgres+Redis
# via the host Docker socket. The host already needs Docker for `make dev`,
# so this adds no new requirement. Use `make test-install` once to provision
# the venv. The ``rm -rf siege_backend.egg-info`` step refreshes stale
# install metadata after we delete a service module (Phase 12 cleanup
# slices) — without it, ``pip install -e .`` keeps the SOURCES.txt
# reference forever.
test-install:
	cd backend && rm -rf siege_backend.egg-info && \
		python -m venv .venv-test && \
		.venv-test/bin/pip install --upgrade pip && \
		.venv-test/bin/pip install -r requirements.txt -r requirements-test.txt

test:
	cd backend && \
		APP_ENV=test \
		SECRET_KEY=$${SECRET_KEY:-test-secret-do-not-use-in-prod-0123456789abcdef0123456789abcdef} \
		ADMIN_PASSWORD=$${ADMIN_PASSWORD:-TestAdminPasswordA1!} \
		ALLOWED_ORIGINS=$${ALLOWED_ORIGINS:-http://localhost:3000} \
		.venv-test/bin/python -m pytest tests/ -v

# Phase 11: walk examples/challenges/ and run every TestCase declared
# in every manifest through the validator registry. No DB required —
# this is the exact entrypoint CI uses.
test-challenges:
	cd backend && \
		PYTHONPATH=$$(pwd) \
		.venv-test/bin/python -m app.tools.test_harness ../examples/challenges

# Phase 12 (slice 16): regenerate the frozen JSON Schema after a
# bluerange-spec model change. Mirrors the snippet in
# docs/challenge-spec-v1.md so authors don't have to copy/paste.
regen-schema:
	cd backend && PYTHONPATH=$$(pwd) .venv-test/bin/python -c "import json; from bluerange_spec import ChallengeManifest; s = ChallengeManifest.model_json_schema(); s['\$$schema'] = 'https://json-schema.org/draft/2020-12/schema'; s['\$$id'] = 'https://seige-range.local/schemas/bluerange-spec/v1/manifest.schema.json'; s['title'] = 'BluerangeChallengeManifest'; s['description'] = 'v1 challenge manifest for the seige-range platform.'; print(json.dumps(s, indent=2, sort_keys=True))" \
		> ../packages/bluerange-spec/src/bluerange_spec/schemas/manifest.schema.json
	@echo "regenerated packages/bluerange-spec/.../manifest.schema.json"

# Phase 12 (slice 20): Playwright E2E suite. Drives the full stack
# via a real browser. Requires:
#   1. ``make test-browser-install`` once (installs node deps +
#      chromium binaries).
#   2. ``make dev`` (or any compose layout exposing the frontend on
#      ${E2E_BASE_URL:-http://localhost:8080}).
#   3. ``ADMIN_PASSWORD`` env var matching the running backend's
#      bootstrap admin password — admin-only specs (challenge seed)
#      need it.
test-browser-install:
	cd frontend && npm install --no-audit --no-fund && npx playwright install --with-deps chromium

test-browser:
	cd frontend && \
		E2E_BASE_URL=$${E2E_BASE_URL:-http://localhost:8080} \
		ADMIN_PASSWORD=$${ADMIN_PASSWORD} \
		npx playwright test

# Phase 12 (slice 15): render the union of every running egress-
# proxied instance's allowlist into a tinyproxy filter file.
# After a successful write, hot-reload tinyproxy with:
#   docker exec siege-egress-proxy kill -HUP 1
render-egress-allowlist:
	cd backend && \
		PYTHONPATH=$$(pwd) \
		.venv-test/bin/python -m app.tools.render_egress_allowlist \
			--target ../docker/egress-proxy/egress-allowlist.conf

health:
	bash scripts/health_check.sh

backup:
	bash scripts/backup.sh

restore:
	@if [ -z "$(FILE)" ]; then echo "Usage: make restore FILE=backups/siege-backup-YYYY-MM-DD.tar.gz"; exit 1; fi
	bash scripts/restore.sh $(FILE)

build:
	docker compose build --no-cache

lint:
	docker compose exec api python -m ruff check app/

# --------------------------------------------------------------------
# Analyst workstation — the in-range jumpbox players SSH/web into
# when they don't have VPN access to their normal toolkit.
# --------------------------------------------------------------------

workstation-build:
	docker compose -f docker-compose.yml \
	               -f infra/workstation/docker-compose.workstation.yml \
	               build workstation

workstation-up:
	@grep -q '^SIEGE_WORKSTATION_PASSWORD=' .env 2>/dev/null \
	    || { echo "set SIEGE_WORKSTATION_PASSWORD in .env first"; exit 1; }
	docker compose -f docker-compose.yml \
	               -f infra/workstation/docker-compose.workstation.yml \
	               up -d workstation

workstation-down:
	docker compose -f docker-compose.yml \
	               -f infra/workstation/docker-compose.workstation.yml \
	               rm -sf workstation

workstation-shell:
	docker exec -it seige-workstation su - analyst

# --------------------------------------------------------------------
# Offline player bundle — for when even the seige-range public host
# isn't reachable (air-gapped lab / customer site with no egress).
# --------------------------------------------------------------------

offline-bundle:
	bash scripts/build-offline-bundle.sh
