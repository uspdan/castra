# LEARNINGS.md — Cross-Project Engineering Learnings

> This file lives in the `engineering-standards` repo and is synced to all projects
> alongside `CLAUDE.md`. It captures learnings promoted from individual project
> memory files that apply universally.
>
> **Promotion criteria**: A learning is promoted here when it has been observed
> in 2+ projects OR is severe enough that one occurrence justifies universal awareness.

---

## UNIVERSAL GOTCHAS

> These have bitten multiple projects. Claude Code should actively check for these.

### LRN-0001: Example — ISO 8601 timestamps must include timezone offset
- **Source projects**: project-alpha (MEM-0002), project-beta (MEM-0015)
- **Learning**: `new Date().toISOString()` emits UTC with `Z` suffix, but many ORMs and logging libraries strip it or assume local time. All projects must use the shared `toUTCTimestamp()` utility that explicitly appends `+00:00`. Bare timestamps without offset are treated as bugs.
- **Impact**: Audit log integrity, cross-service event ordering

---

## UNIVERSAL PATTERNS

> Approaches proven across multiple projects. Preferred defaults for new work.

### LRN-0002: Example — Structured error context beats stack traces for debugging
- **Source projects**: project-alpha (MEM-0009), project-gamma (MEM-0003)
- **Learning**: In production, stack traces are near-useless for business logic bugs. The `context` field on `AppError` (carrying request ID, entity IDs, operation name, and input summary) resolves 80% of issues from logs alone. Always populate error context — never throw bare Error objects.
- **Impact**: Mean time to resolution, on-call burden

---

## DEPENDENCY ADVISORIES

> Cross-project dependency warnings. Check before upgrading.

### LRN-0003: Example — Zod v4 migration requires schema rewrite
- **Source projects**: project-beta (MEM-0022)
- **Learning**: Zod v4 is not backward-compatible with v3 schemas. `.transform()` chains, `.refine()` signatures, and error formatting all changed. Budget 2-4 hours per project for migration. Pin to v3 until all projects can migrate together.
- **Impact**: Validation layer, API contracts, config parsing

---

## ANTI-PATTERNS

> Things that seemed like good ideas but weren't. Don't repeat these.

### LRN-0004: Example — Don't use database triggers for audit logging
- **Source projects**: project-alpha (MEM-0011), project-delta (MEM-0007)
- **Learning**: DB triggers for audit logs seemed appealing (guaranteed capture) but caused: 1) audit entries missing `who` and `why` (DB layer doesn't have request context), 2) 30% write latency increase on hot tables, 3) migration nightmares when schema changed. Application-layer audit logging with the six-question standard is superior in every case.
- **Impact**: Audit integrity, write performance, maintainability
