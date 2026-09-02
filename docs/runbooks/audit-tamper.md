# Runbook — Audit ledger tamper detected

**Estimated time:** 30–90 minutes (longer if the DB restore path is taken).

## Symptom

Any of:

- The `AuditLedgerTamper` page alert fired
  (`increase(siege_audit_tamper_findings_total[1h]) > 0`).
- "Audit ledger tamper detected" in the admin notification drawer
  (the hourly scheduler broadcasts on every finding).
- Structured `ERROR` log line `audit_ledger.tamper_detected`.
- [`prod-smoke.md`](prod-smoke.md) step 4 exited non-zero.

## What it means

The ledger is an append-only hash chain: each row commits to the previous
row's hash. The hourly verifier re-walks the whole chain. A finding means a
row was **deleted, reordered, or modified after being written** — or the
verifier hit an inconsistency from a partial restore. This is either an
attacker with database write access or an operational mistake (e.g. a
restore from mid-chain backup). Treat it as an incident until proven
operational.

## Decision tree

1. **Did a DB restore, migration, or manual `audit_ledger` surgery happen
   recently?** → Likely operational. Continue below to classify, then
   document; the chain will not self-heal (see step 5).
2. **No recent operational cause?** → Assume compromise. Continue below
   AND start credential rotation ([`secret-rotation.md`](secret-rotation.md))
   in parallel — a writer that can alter the ledger has DB credentials.

## Steps

### 1. Capture the evidence before anything else

```bash
docker compose -f /opt/siege-range/docker-compose.prod.yml \
  exec -T api python -m app.tools.audit_verify --json \
  > /root/audit-tamper-$(date -u +%Y%m%dT%H%M%SZ).json
```

Exit codes: `0` intact, `1` tamper (findings in the report), `2`
operational failure (DB unreachable — different problem, see
[`db-restore.md`](db-restore.md) triage).

### 2. Snapshot the ledger table

```bash
docker compose -f /opt/siege-range/docker-compose.prod.yml \
  exec -T db pg_dump -U siege -t audit_ledger siege_range \
  > /root/audit-ledger-snapshot-$(date -u +%Y%m%dT%H%M%SZ).sql
```

Do this **before** any restore or cleanup — the tampered state is itself
evidence.

### 3. Classify the findings

Each finding in the JSON report has a `kind`:

| `kind` | Meaning |
|---|---|
| `seq_gap` | Row(s) deleted — the sequence skips. |
| `prev_hash_mismatch` | A row no longer commits to its predecessor — insertion or reordering. |
| hash mismatch (recomputed ≠ stored) | Row contents were edited in place. |

A single cluster at the chain tail usually means an interrupted write or a
restore from an older backup. Findings scattered mid-chain mean deliberate
editing.

### 4. Corroborate against off-host data

- Compare against the most recent nightly backup's `audit_ledger` rows.
- Check Postgres logs for `UPDATE`/`DELETE` on `audit_ledger` (the
  application only ever `INSERT`s).
- Check `docker compose logs api` around the earliest affected row's
  `created_at`.

### 5. Recover

The ledger is append-only by design — there is **no repair-in-place**.
Choose one:

- **Restore path** (needed when other tables are also suspect): follow
  [`db-restore.md`](db-restore.md) to the last backup whose chain verifies
  clean, accepting the data-loss window.
- **Accept-and-document path** (operational cause, damage limited to the
  ledger): leave the chain as-is, file the incident record with the two
  artefacts from steps 1–2. The verifier will keep reporting the same
  findings — expected and correct; the alert's `for: 1m` window means it
  re-fires each hour until the underlying rows are restored. Silence the
  alert with an annotated Alertmanager silence bounded to the incident
  ticket, never permanently.

### 6. If compromise is confirmed

Complete [`secret-rotation.md`](secret-rotation.md) (DB password,
`SECRET_KEY`, webhook secrets), review admin accounts and API tokens
created since the earliest finding, and export the drill/audit evidence
for the affected window before rotating.

## Verification

```bash
docker compose -f /opt/siege-range/docker-compose.prod.yml \
  exec -T api python -m app.tools.audit_verify
# Expected after a restore: exit 0, "audit-ledger OK — N rows"
```

Note: `siege_audit_tamper_findings_total` is a cumulative counter — it
never decreases. The alert clears when the counter stops increasing, one
hour after the last failing verify run.

## After-action

- Attach the step-1 JSON report and step-2 SQL snapshot to the incident
  record.
- If the cause was a partial restore: update [`db-restore.md`](db-restore.md)
  usage notes so the next restore verifies the chain immediately.
- If the cause was compromise: schedule a full secrets rotation audit and
  review how the writer obtained DB access.
