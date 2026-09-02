# Runbooks

Operator-facing procedures for production incidents and routine
maintenance. Each runbook is structured: **symptom**, **decision
tree**, **copy-paste-executable steps**, **verification**,
**after-action**, **estimated time**.

CLAUDE.md §9.2 expects a runbook for every known failure mode:

| File | When |
|---|---|
| [`rollback.md`](rollback.md) | A bad release is in production; back it out. |
| [`db-restore.md`](db-restore.md) | Schema corruption / data loss / catastrophic migration. |
| [`secret-rotation.md`](secret-rotation.md) | Key leaked; quarterly hygiene; pre-prod handover. |
| [`scheduler-stuck.md`](scheduler-stuck.md) | TTL reaper / webhook retries / leaderboard cache aren't firing. |
| [`egress-allowlist.md`](egress-allowlist.md) | Tinyproxy filter hot-reload pipeline; manual refresh; rollback to static mode. |
| [`prod-smoke.md`](prod-smoke.md) | Post-deploy verification matrix for `make prod` against a real TLS host. |
| [`llm-honeypot-operator.md`](llm-honeypot-operator.md) | Deploying + maintaining LLM honeypot challenges (ADR 001 / `llm-sandbox` profile). |
| [`audit-tamper.md`](audit-tamper.md) | Audit-ledger tamper alert fired; chain verification failing. |
| [`offline-workstation.md`](offline-workstation.md) | Building the offline bundle; air-gapped play. |

Future additions (file an issue if you hit a failure mode not
covered):

- TLS certificate renewal / expiry
- Webhook receiver storm (10× expected delivery rate)
- VPN tunnel drop affecting a live competition

## When writing a new runbook

1. Start from one of the shipped files. Steal structure, drop
   in your steps.
2. Every command must be copy-paste-executable. No "edit
   `<the right file>`" without the path.
3. Include verification steps. If you can't verify the fix worked,
   the runbook isn't done.
4. Include estimated time. Operators need to know whether to grab a
   coffee or stay at the keyboard.
5. End with an after-action section so the next operator catches the
   same pattern earlier.
