# Runbook — operating LLM honeypot challenges

## When to use

You're deploying or maintaining a challenge that uses the
``llm-sandbox`` container profile + the ``llm_signal`` validator
(ADR 0001). The reference challenge is in
``examples/challenges/llm-customer-pii/``.

## Estimated time

~10 minutes for first-time setup of the inference endpoint, ~2
minutes per challenge afterwards.

## Architecture

```
┌─────────┐  HTTP POST    ┌────────────────┐   HTTPS   ┌──────────────┐
│ player  │ ──────────────▶│  challenge     │ ─────────▶│  inference   │
│ browser │                │  container     │           │  endpoint    │
│         │                │  (llm-sandbox) │           │  (operator-  │
└─────────┘                └────────────────┘           │   supplied)  │
                                  │                     └──────────────┘
                                  ▼
                         transcript captured
                                  │
                                  ▼
                          POST /api/v1/challenges/<slug>/submit
                          ↓
                          llm_signal validator regex-matches transcript
                          ↓
                          challenge solved iff ≥ min_matches patterns hit
```

The ``llm-sandbox`` profile is functionally a thin wrapper around
``egress-proxied``: the challenge container can reach exactly the
hosts in ``container.egress_allowlist`` (the inference endpoint,
nothing else). All other Phase-9 hardening (read_only,
``cap_drop=ALL``, seccomp default-strict, no-new-privileges) is
unchanged.

## Operator setup — first time

### 1. Provision an inference endpoint

The platform doesn't host the LLM. Pick one and capture two
values:

| Variable | What it is |
|---|---|
| ``LLM_ENDPOINT_URL`` | Base URL the challenge container POSTs prompts to. OpenAI-compatible chat-completions schema. |
| ``LLM_ENDPOINT_KEY`` | API key the container sends in ``Authorization: Bearer …``. Per-instance rotation is recommended. |

Examples:

- ``https://api.openai.com/v1/chat/completions`` + an OpenAI key
- ``https://api.anthropic.com/v1/messages`` + an Anthropic key
- ``https://llm.internal.example.com/v1/chat/completions`` + a
  per-deployment key for a self-hosted model (vLLM, llama.cpp,
  TGI)

Whichever you pick, set ``temperature=0`` and a fixed ``seed`` (where
the upstream supports it) in the challenge container's request
body. Determinism is the validator's friend.

### 2. Allowlist the inference host on the challenge

Edit ``container.egress_allowlist`` in the challenge manifest to
include exactly the inference host. The hot-reload pipeline in
``docs/runbooks/egress-allowlist.md`` picks up the change at next
launch.

### 3. Wire the env vars at deploy

Inject the URL + key into the running container via
``docker_config.environment`` on the manifest:

```yaml
container:
  image: "siege/llm-customer-support"
  port: 8080
  profile: llm-sandbox
  egress_allowlist:
    - "api.openai.com"
  environment:
    LLM_ENDPOINT_URL: "https://api.openai.com/v1/chat/completions"
    LLM_ENDPOINT_KEY: "${LLM_ENDPOINT_KEY}"  # secret manager
```

(If your secret manager doesn't substitute, swap to a
docker-secret mount or a per-instance env via the launcher's
``challenge.docker_config.environment`` JSON.)

## Authoring a new LLM honeypot challenge

1. Fork ``examples/challenges/llm-customer-pii/manifest.yaml``.
2. Pick the regex signals — what string shapes does a successful
   jailbreak emit? PII shapes (SSN, credit card, date of birth),
   internal codenames, profanity / harmful-output markers, etc.
3. Set ``min_matches`` ≥ the number of distinct signals you
   require for a "complete capture". Default is 1 (any single
   signal counts).
4. Write the challenge container — a small FastAPI / Express
   service that accepts the player's prompt, forwards it to the
   inference endpoint with the system prompt that encodes the
   "trap", captures the assistant's full reply, and returns the
   transcript verbatim. The transcript is what the player POSTs
   to ``/api/v1/challenges/<slug>/submit``.
5. Pin the docker image digest (Phase 9 launcher refuses without
   it) and push to your registry.
6. ``make seed`` (or the v1 admin seed endpoint) loads the
   manifest into the platform.

## Validator behaviour

- **Pattern engine**: re2 if installed (linear-time, ReDoS-immune),
  otherwise stdlib ``re`` with a ``WARN`` log at validator import.
- **Search semantics**: ``re.search`` (substring) — the transcript
  is a multi-line conversation, not a single token. Anchor your
  patterns explicitly if you need stricter matching.
- **Audit trail**: matched pattern strings are echoed into the
  validator's ``details`` dict and end up in the audit ledger
  (event ``challenge.flag.submit.pass``). Useful for "why did
  this submission count?" investigations.

## Failure modes

- **Inference endpoint rate-limits the challenge container** —
  the egress proxy doesn't retry. Document the rate limit in the
  challenge description so players don't blame the platform.
  Consider a per-instance API key with its own quota.
- **Player abuse of the inference endpoint** — they can POST
  arbitrary prompts. If you're paying per-token, set a token
  budget per instance (challenge container enforces, not the
  platform).
- **False positives** — overly broad patterns will award points
  for incidental matches. Ship a regression corpus of "this
  transcript should NOT pass" alongside your challenge and re-run
  it via ``make test-challenges`` after every pattern edit.

## Rollback

If a deployed LLM honeypot challenge starts misfiring:

1. Soft-delete via Admin → Challenges → trash icon (sets
   ``is_active=False``).
2. Players who already solved keep their points (Solve rows are
   immutable).
3. Edit the manifest's patterns offline, re-seed, then release
   under a new slug to make the change explicit.

## See also

- ``docs/adr/0001-ai-honeypot-category.md`` — the design decisions
  this runbook implements.
- ``docs/runbooks/egress-allowlist.md`` — the hot-reload pipeline
  the per-challenge allowlist rides on.
