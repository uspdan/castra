# ADR 0001: AI / LLM honeypot challenge category

- **Status**: Proposed
- **Date**: 2026-05-04
- **Deciders**: Daniel Hay
- **Context tag**: blue-team training, manifest v1+

## Context

`BACKLOG.md` proposes a challenge category for blue-team training
against prompt-injection, jailbreak, model-extraction, and
agent-abuse scenarios. The shape, hosting model, and grading story
were left unresolved, deliberately deferred until Phase 12 / v1
contract had soaked. Phase 12 + Sprints 1–5 have shipped; this ADR
locks in the design so the category can be implemented when needed.

Three open questions block scoping:

1. **Hosting** — does the platform host the honeypot LLM (cost,
   GPU) or accept a BYO inference URL?
2. **Determinism** — how to grade reliably given LLM
   non-determinism?
3. **Authoring secrecy** — how do we vet an honeypot challenge's
   "correct" bait without leaking it via the manifest?

## Decision

### 1. Hosting model: BYO inference URL via per-instance env var

The platform does **not** host the inference endpoint. Each
challenge instance is provisioned with `LLM_ENDPOINT_URL` and
`LLM_ENDPOINT_KEY` env vars pointing at an operator-supplied
inference service (OpenAI-compatible chat-completions API). The
operator wires this into `docker_config.environment` on the
challenge manifest at deploy time.

**Why:**
- Mirrors the existing `egress-proxied` profile pattern: the
  challenge container talks out through a controlled allowlist;
  no compute lives inside the platform.
- Keeps the platform out of the GPU-billing business.
- Lets the operator pick the model class (gpt-4 / claude-sonnet /
  llama via vLLM / etc.) per challenge.
- Per-instance rotation of `LLM_ENDPOINT_KEY` is trivial via the
  operator's secrets manager — no platform-side key store needed.

**Implications:**
- A new manifest field `container.llm_endpoint_required: bool` —
  when true, the launcher fails fast if the env vars aren't
  present.
- A new container profile `llm-sandbox` (or extend
  `egress-proxied` with the inference endpoint added to the
  allowlist) so the egress allowlist permits exactly the
  inference host and nothing else.
- Operator runbook addition: how to provision the env vars, how
  to rotate, how to scope the API key.

### 2. Determinism: classifier-based grading, not output equality

The validator does **not** compare LLM output strings. Instead:

- The manifest declares one or more `expected_signal` patterns:
  - **Regex** patterns over the LLM output (e.g. presence of a
    leaked PII format `\d{3}-\d{2}-\d{4}` SSN-like).
  - **Classifier** calls — the validator submits the LLM
    output to a labelled detector (e.g. a separate small model
    or a regex-ensemble) and the boolean verdict is the grade.
- The platform itself is configured to call the inference endpoint
  with `temperature=0`, fixed `seed` where the upstream supports
  it (OpenAI does, Anthropic does via experimental APIs, llama.cpp
  does), and a pinned model version.
- Where determinism still drifts (rare classifier disagreements),
  grading is **lenient**: any of the listed signals counts as a
  capture. Authors are expected to phrase signals broadly.

**New validator plugin: `llm_signal`.** Builds on the existing
Phase 8 validator-registry pattern (cf.
`backend/app/validators/regex.py` for the closest analogue).
Signature:

```python
class LlmSignalValidator(BaseValidator):
    name = "llm_signal"
    config_schema = {
        "patterns": List[str],   # regexes
        "classifier": Optional[str],  # named classifier id
        "threshold": Optional[float],  # for soft classifiers
    }
```

The flag dispatch passes the LLM-output transcript captured from
the challenge container as the validator's input.

### 3. Authoring secrecy: encrypted manifest section + sealed at load

Honeypot bait (the ground-truth signal) must not be discoverable
from the manifest by competitors who can read shipped artifacts.

- New manifest field `flags[].secret_bundle` — a
  base64-encoded ciphertext blob. Encrypted with libsodium
  `crypto_secretbox` using a key derived from
  `BLUERANGE_SECRET_BUNDLE_KEY` (env var, fail-fast if unset
  in production per CLAUDE.md §3.2). The plaintext is the JSON
  config the validator needs (regex patterns, classifier ids,
  thresholds).
- The challenge loader (`backend/app/services/challenge_loader/`)
  decrypts at load time and stores the plaintext config on the
  `ChallengeFlag` row — same `config` JSONB column as today.
  The encrypted manifest stays on disk.
- The validator subprocess receives the plaintext via the
  existing sandboxed stdin path (Phase 8 sandbox); it never sees
  `BLUERANGE_SECRET_BUNDLE_KEY` itself.
- Authors run `make encrypt-bundle` (a thin CLI wrapper around
  `nacl.secret.SecretBox.encrypt`) to seal the bundle before
  committing the manifest.

**Trade-off accepted:** the operator must protect
`BLUERANGE_SECRET_BUNDLE_KEY` like any other production secret.
A leaked key compromises every honeypot challenge's grading
config but does NOT compromise the platform — it only lets a
sophisticated competitor inspect the validator's expected signals.

## Reference challenge

"Fake customer-support agent leaks PII when asked just-so":

- Manifest declares profile `egress-proxied-sidecar` (or
  `llm-sandbox` once added) with the inference URL on the
  allowlist.
- Challenge container is a simple FastAPI front-end calling the
  inference endpoint with a system prompt that encodes the
  vulnerability ("you are a customer-support agent, you have
  access to recent customer records: …").
- `flags[0].flag_type = "llm_signal"`, `secret_bundle` encrypts
  `{"patterns": ["\\d{3}-\\d{2}-\\d{4}", "\\d{16}"]}`.
- Player crafts the prompt that elicits a PII leak; the platform
  detects, awards points, audits.

## Status & next steps

This ADR is **Proposed**. Implementation is queued for a future
sprint and gated on user sign-off here.

When ready to implement, the ordered shopping list:

1. Validator plugin `llm_signal` in `backend/app/validators/`.
2. Container profile `llm-sandbox` (or extend `egress-proxied`
   with allowlist injection).
3. `BLUERANGE_SECRET_BUNDLE_KEY` config + loader decrypt path.
4. `make encrypt-bundle` author CLI tool.
5. Reference challenge in `examples/challenges/llm-customer-pii/`.
6. Runbook in `docs/runbooks/llm-honeypot-operator.md` covering
   env-var provisioning and key rotation.

## Alternatives considered

- **Platform-hosted inference.** Rejected: GPU cost, abuse risk,
  scaling concerns, complicates the threat model.
- **Output-equality grading.** Rejected: LLMs drift across
  upstream model updates even at temp=0; the platform would
  silently break existing challenges.
- **Cleartext manifest bait.** Rejected: any competitor with
  manifest access (e.g. via leaked `examples/challenges/`)
  would have the answer key.
