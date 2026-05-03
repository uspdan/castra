# Runbooks

Operator-facing procedures for production incidents and routine
maintenance. Each runbook is structured: **symptom**, **decision
tree**, **copy-paste-executable steps**, **verification**,
**after-action**, **estimated time**.

CLAUDE.md §9.2 expects a runbook for every known failure mode.
Sprint 1 ships the four most critical:

| File | When |
|---|---|
| [`rollback.md`](rollback.md) | A bad release is in production; back it out. |
| [`db-restore.md`](db-restore.md) | Schema corruption / data loss / catastrophic migration. |
| [`secret-rotation.md`](secret-rotation.md) | Key leaked; quarterly hygiene; pre-prod handover. |
| [`scheduler-stuck.md`](scheduler-stuck.md) | TTL reaper / webhook retries / leaderboard cache aren't firing. |
| [`egress-allowlist.md`](egress-allowlist.md) | Tinyproxy filter hot-reload pipeline; manual refresh; rollback to static mode. |

Future additions (file an issue if you hit a failure mode not
covered):

- TLS certificate renewal / expiry
- Webhook receiver storm (10× expected delivery rate)
- VPN tunnel drop affecting a live competition
- Audit ledger tamper detection (`audit_verify` exits 1)

## When writing a new runbook

1. Start from one of the four shipped files. Steal structure, drop
   in your steps.
2. Every command must be copy-paste-executable. No "edit
   `<the right file>`" without the path.
3. Include verification steps. If you can't verify the fix worked,
   the runbook isn't done.
4. Include estimated time. Operators need to know whether to grab a
   coffee or stay at the keyboard.
5. End with an after-action section so the next operator catches the
   same pattern earlier.
