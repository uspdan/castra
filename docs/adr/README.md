# Architectural Decision Records

One file per significant technical decision: context, decision,
consequences. Copy [`000-template.md`](000-template.md) to start a new one;
number it after the highest existing ADR.

| ADR | Decision | Status |
|---|---|---|
| [001](001-ai-honeypot-category.md) | AI / LLM honeypot challenge category (`llm-sandbox` profile, `llm_signal` validator) | Accepted |
| [002](002-orchestrator-socket-proxy.md) | Orchestrator hardening — docker-socket-proxy + container profile registry | Accepted |
| [003](003-workstation-security.md) | Analyst workstation security posture | Accepted |
| [004](004-validator-network-isolation.md) | Network isolation (seccomp netns) for subprocess validators | Accepted |
| [005](005-artifact-only-challenges.md) | Artifact-only challenges; per-instance flags | Part 1 implemented; part 2 accepted-in-principle |
| [006](006-orchestrator-socket-trust-boundary.md) | Orchestrator socket trust boundary (audit finding R26) | Accepted |
| [007](007-ttyd-shell-trust-boundary.md) | ttyd in-browser shell trust boundary (audit finding R20) | Accepted |
