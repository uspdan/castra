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

## Loading into Prometheus

```yaml
# /etc/prometheus/prometheus.yml
rule_files:
  - /etc/prometheus/rules/api.rules.yml
  - /etc/prometheus/rules/audit.rules.yml
```

Then `kill -HUP $(pidof prometheus)` (or restart) to pick up
changes. `promtool check rules /etc/prometheus/rules/*.yml` is
the local lint pass.

## Scrape config

The API exposes `/metrics` on the standard service port (8000
inside docker-compose). A typical scrape entry:

```yaml
scrape_configs:
  - job_name: siege-range-api
    metrics_path: /metrics
    static_configs:
      - targets: ['api:8000']
        labels:
          service: siege-range
          env: production  # or staging
```

The `up{job="siege-range-api"}` series referenced by
`SiegeApiDown` exists by virtue of the scrape job's name.

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

## Testing rules locally

`promtool` ships a unit-test runner:

```bash
promtool test rules tests/unit/*_test.yml
```

Test files for these rules aren't shipped yet — future sprint.
For now, sanity-check by booting Prometheus with the rules
loaded against the local `make dev` stack and posting a
synthetic 5xx burst to see `SiegeApiHighErrorRate` fire after
its 5-minute hold.
