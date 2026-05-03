# BACKLOG.md — feature requests not in current scope

## AI / LLM honeypot modules
*Added: 2026-05-01*

Challenge category for blue-team training against prompt-injection,
jailbreak, model-extraction, and agent-abuse scenarios. Likely shape:

- New manifest category (e.g. `ai-honeypot`) under the v1 spec (Phase 7
  contract; would be additive in v1.1 or breaking in v2 depending on
  enum extension policy decided then).
- Validators specific to LLM evaluation: `prompt-injection-detected`
  (run a target prompt through a sandboxed LLM and check the
  submission against guardrail signals), `jailbreak-attempt`
  (regex/classifier match on harmful-output indicators),
  `agent-abuse-trace` (validate a chain of tool calls against an
  expected attack pattern).
- Container profile likely `network-isolated` or a new
  `llm-sandbox` profile that allows egress only to a designated
  inference endpoint via the egress allowlist (Phase 9 supports this).
- Reference challenge: e.g. "fake customer-support agent leaks PII when
  asked just-so" — players craft the prompt, validator confirms PII
  emission against a labeled corpus.
- Open design questions to resolve before scoping:
  - Does the platform host the honeypot LLM (cost, GPU) or accept a
    BYO inference URL via per-instance env?
  - How to make grading deterministic given LLM non-determinism
    (temp=0, fixed seed where supported, or output-pattern matching)?
  - Authoring-time review: how do we vet an honeypot challenge's
    "correct" bait without leaking it via the manifest?

**Not in scope for the current 12-phase hardening.** Revisit after
Phase 12 lands and the v1 contract has soaked.
