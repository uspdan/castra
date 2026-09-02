# Security Policy

Castra is a security-drill platform, so we hold it to the standard we help
teams train for.

## Reporting a vulnerability

**Do not open a public issue for security reports.**

Use GitHub's private reporting: **Security → Report a vulnerability** on
[uspdan/castra](https://github.com/uspdan/castra/security/advisories/new).

Please include:

- A description of the issue and its impact.
- Steps or a proof-of-concept to reproduce it.
- The version or commit you tested (`git rev-parse HEAD`, or the image tag).

You will get an acknowledgement within **72 hours** and a triage verdict
within **7 days**. We ask for coordinated disclosure: give us **90 days**
(or a mutually agreed window) before publishing details.

## Supported versions

| Version | Supported |
| ------- | --------- |
| Latest release (`v2.5.x`) | ✅ |
| `main` | ✅ (rolling) |
| Older tags | ❌ |

## Scope notes

- Challenge containers are **intentionally vulnerable by design** — flaws in
  challenge content are only in scope if they let a participant escape the
  sandbox boundary or reach the control plane.
- The platform's own surfaces (API, frontend, orchestrator, validators,
  auth, audit ledger) are fully in scope.
- Denial-of-service reports require demonstrated asymmetric impact.

## Hardening baseline

The platform ships with an append-only hash-chained audit ledger, strict
input validation at every boundary, per-user rate limiting, and a
socket-proxied container sandbox. See `docs/` for the architecture decisions
behind these controls.
