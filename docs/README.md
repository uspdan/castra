# Castra documentation

Start with the handbook that matches your role:

| I want to… | Read |
|---|---|
| **Deploy and operate a range** | [Operator handbook](operator-handbook.md) — Day-1 install (bootstrap, TLS, bring-up) and Day-2 ops (monitoring, backups, MFA, upgrades). Then verify with the [production smoke checklist](runbooks/prod-smoke.md). |
| **Play — take the drills** | [Player handbook](player-handbook.md) — UI flow, the in-range analyst workstation, and fully offline play. |
| **Write challenges** | [Author handbook](author-handbook.md) — the `castra` SDK, manifest anatomy, container profiles, authoring checklist. |

## Reference

- [Challenge manifest spec v1](challenge-spec-v1.md) — the locked on-disk
  format (normative; the author handbook is the tutorial).
- [Security model](security-model.md) — container isolation, seccomp
  profiles, capability drops, trust boundaries.
- [Threat-hunt coverage](threat-hunt-coverage.md) — ATT&CK / D3FEND map of
  the challenge catalogue.
- [ADRs](adr/) — architectural decision records, indexed.

## Operations

- [Runbooks](runbooks/) — one file per known failure mode, indexed;
  symptom → decision tree → copy-paste steps.
- [Alert rules](alerts/) — drop-in Prometheus rules with promtool unit
  tests.
- [CI templates](ci-templates/) — reference workflows for forks.

## For operators with compliance duties

- [Privacy notice](privacy.md) — what personal data the platform touches.
- [DPIA](dpia.md) — GDPR Art. 35 assessment template for your deployment.
