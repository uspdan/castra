# Prometheus alert rules

CLAUDE.md §14.4 requires every service to ship its own alert
definitions in the repo, with each alert linked to a runbook.
This directory holds the canonical Prometheus rule files for
the seige-range API.

## Files

| File | What it watches |
|---|---|
| [`api.rules.yml`](api.rules.yml) | HTTP error rate, p99 latency, in-flight saturation, `up` liveness gauge. |
| [`audit.rules.yml`](audit.rules.yml) | Audit-ledger verify heartbeat + tamper finding counter. |
| [`backup.rules.yml`](backup.rules.yml) | Nightly `pg_dump` heartbeat, failure counter, dump size. |

## These are wired up

They weren't, for a long time. The rules sat here evaluated by
nobody, which is how a nightly backup that failed on every single
run went unnoticed for days — the job logged an error, APScheduler
logged "executed successfully", and no one was watching either.

`docker-compose.yml` now runs Prometheus and Alertmanager:

- **Prometheus** (`:9090`) scrapes `api:8000/metrics` every 15s and
  evaluates this directory, bind-mounted read-only at
  `/etc/prometheus/rules`. It is mounted, not copied, so what CI
  validates and what Prometheus evaluates are the same bytes.
- **Alertmanager** (`:9093`) routes on the `severity` label.

Both sit on the `internal: true` `siege-backend` network, so
`/metrics` is reachable by the scraper without being exposed
publicly.

Config lives in [`infra/observability/`](../../infra/observability/).
Note that neither Prometheus nor Alertmanager expands environment
variables in its config file — anything environment-specific has to
be a command-line flag in compose, not a `${VAR}` placeholder, which
would be read literally.

### Finishing the loop

Alerts are evaluated, grouped, inhibited and visible in the
Alertmanager UI out of the box, but **delivery is not configured** —
there is no sensible default destination for someone else's pager.
Put a real Slack/Teams/PagerDuty webhook in
`infra/observability/webhook-url` and restart Alertmanager. The URL
is read from that file at send time, so it can be rotated without a
rebuild and never enters git history.

## Conventions the CI job enforces

- `severity` must be `page` or `warn`. Those are the only values
  `alertmanager.yml` routes on; anything else falls through to the
  default receiver instead of paging. The backup rules were first
  written with `critical`/`warning` and would have done exactly that.
- Every rule needs a `runbook_url` resolving to a real file under
  `docs/runbooks/`. A dangling link is worse than none — it looks
  handled.
- Every `*.rules.yml` here must appear in `rule_files` in
  `prometheus.yml`, or it is a text file.

`backend/tests/unit/test_alert_rules.py` checks all three.

## Authoring new rules

1. Pick a metric exposed by `app/middleware/metrics.py` or by
   a service module's `Counter`/`Gauge`/`Histogram`.
2. Add the rule to the appropriate group (or create a new
   group file alongside an explanatory README entry above).
3. Every rule MUST carry an `annotations.runbook_url` pointing
   at a file under `docs/runbooks/`. If the corresponding
   runbook doesn't exist, write it first — alerts without
   runbooks are pager-noise per CLAUDE.md.
4. Set `severity: page` only for true wake-someone-up
   conditions; use `warn` for everything else and let the
   Alertmanager routing tree handle escalation.

## Testing rules

Test files now ship in [`tests/`](tests/) and run in CI
(`alert-rules — promtool validate + unit tests`):

```bash
docker run --rm -v "$PWD/docs/alerts:/alerts:ro" \
  --entrypoint promtool prom/prometheus:v3.7.3 \
  test rules /alerts/tests/*_test.yml
```

`backup_test.yml` uses `alert_rule_test`, asserting the full alert
including annotations. The other two use `promql_expr_test`, which
checks the expression trips at the right threshold without pinning
several paragraphs of operator prose that would break on every
wording tweak. `exp_alerts` compares the *entire* annotation map —
there is no partial match — so that distinction is deliberate, not
laziness.

Each file covers both directions: the condition firing, **and** a
healthy series staying quiet. A rule that pages every night on a
working system gets muted, which is the same outcome as no rule.
