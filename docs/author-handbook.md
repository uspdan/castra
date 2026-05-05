# Challenge author handbook

How to write a challenge that ships on siege-range. Pairs with
the v1 manifest schema in
`packages/bluerange-spec/src/bluerange_spec/schemas/manifest.schema.json`
and the worked examples in `examples/challenges/`.

## What a challenge is

A directory under `examples/challenges/` (or wherever your
operator's challenge source lives) containing:

```
my-challenge/
├── manifest.yaml          # required — the spec
├── artifacts/             # optional — files the challenge ships
│   └── ...
└── container/             # optional — Dockerfile + service
    └── ...
```

The platform reads the manifest, hashes the artefact files,
launches the container per the manifest's `container.profile`,
and grades flag submissions through the validator named by
`flags[].type`.

## The 30-second example

```yaml
# yaml-language-server: $schema=../../packages/bluerange-spec/src/bluerange_spec/schemas/manifest.schema.json
spec_version: "1"
slug: my-first-challenge
title: "My First Challenge"
description: |
  Find the flag in the container's banner.

team: red
category: web
difficulty: 1
points: 100

container:
  image: "siege/example-banner"
  digest: "sha256:abcdef0123456789..."   # required — see Pinning below
  port: 8080
  profile: default-strict

flags:
  - id: primary
    type: exact
    points: 100
    label: "Banner flag"
    value: "CTF{REDACTED}"

tests:
  cases:
    - name: "exact flag passes"
      flag_id: primary
      submission: "CTF{REDACTED}"
      expected: pass
    - name: "wrong flag fails"
      flag_id: primary
      submission: "CTF{REDACTED}"
      expected: fail
```

Run `make test-challenges` to walk every challenge under
`examples/challenges/` through its `tests.cases` matrix without
spawning containers.

## Anatomy of the manifest

### Top-level identity

| Field | Notes |
|---|---|
| `spec_version` | Always `"1"` for now. Bumps require platform-side migration. |
| `slug` | URL-safe identifier; lowercase alphanumeric + hyphens. Must be globally unique. |
| `title` | Human-friendly; shown in the catalogue and on the leaderboard. |
| `description` | Markdown. Players see this on the challenge detail page. |
| `team` | `red` or `blue`. Drives the scoreboard split. |
| `category` | Free-form string. The catalogue lets users filter by it. |
| `difficulty` | 1–5. Influences sort order. |
| `points` | The challenge's headline points. Per-flag points override this when you ship multi-flag challenges. |

### `container.*`

| Field | Required | Notes |
|---|---|---|
| `image` | yes | OCI reference, lowercase, no digest in this field. |
| `digest` | yes (in production) | `sha256:<64hex>` pin. The launcher refuses un-pinned images. |
| `port` | yes | Port the player connects to via the assigned host port. |
| `profile` | default `default-strict` | One of: `default-strict`, `malware-sandbox`, `egress-proxied`, `egress-proxied-sidecar`, `llm-sandbox`. |
| `egress_allowlist` | only with egress profiles | List of FQDNs the container can reach. |
| `environment` | optional | Env vars threaded into the container. Use this for per-instance secrets. |

#### Container profiles cheat-sheet

| Profile | When |
|---|---|
| `default-strict` | Self-contained challenge. No outbound network. Most challenges. |
| `malware-sandbox` | Tighter limits (fewer pids, less memory, shorter TTL). Use for actually-malicious payloads. |
| `egress-proxied` | Container needs limited outbound — list FQDNs in `egress_allowlist`. Shared proxy. |
| `egress-proxied-sidecar` | Same shape, but a per-instance proxy. Use when allowlists shouldn't bleed across challenges. |
| `llm-sandbox` | LLM-honeypot challenges that talk to an inference endpoint. ADR 0001. |

### `flags[]`

A challenge can declare multiple flags. The validator engine
dispatches on `type`:

| `type` | What it does |
|---|---|
| `exact` | Cleartext equality. Server stores the hash. |
| `regex` | Pattern match (re2 if available). |
| `multi_part` | Ordered list of sub-flags. |
| `sigma_rule` | Player submits a Sigma rule; we run it against a fixture event log. |
| `yara_rule` | Player submits a YARA rule; we run it against staged samples. |
| `chain_of_custody` | Player submits a JSON evidence-handling timeline. |
| `attack_chain` | Player submits an ATT&CK technique sequence. |
| `cloud_misconfig` | Player enumerates findings in a fixture IaC bundle. |
| `llm_signal` | Player submits an LLM transcript; we regex-match for signal patterns. |

Each type has its own required config keys — see the schema or
`examples/challenges/` for the canonical shapes. **A custom
validator** can be plugged in via the `bluerange.validators`
entry-point group; see
`backend/app/validators/llm_signal.py` for the smallest possible
example.

### `hints[]`

Each hint costs points (deducted on first unlock). Authors set
`cost`; the platform enforces.

```yaml
hints:
  - text: "Try the /api endpoint."
    cost: 25
  - text: "The header X-Auth uses HS256 with a weak key."
    cost: 75
```

### `prerequisites[]`

Challenge slugs the player must solve before this one becomes
submittable. Returns a structured 412 with `missing_slugs` if
the player tries early — the frontend surfaces the list.

### `tests.cases[]`

Local test matrix the harness walks. Each case names a
`flag_id`, a synthetic `submission`, and an `expected` outcome
(`pass` / `fail`). Run via `make test-challenges`.

Authors should ship at least:
- one `pass` case per flag (the reference correct submission)
- one `fail` case per flag (a near-miss)

For `llm_signal`, ship cases with realistic transcript shapes
both for guarded refusals and for jailbroken leaks.

## Pinning the image digest

Once you've built + pushed your challenge container:

```bash
docker buildx imagetools inspect --raw siege/example-banner:latest \
  | jq -r '.manifests[0].digest'
# OR if you've pushed with docker push:
docker inspect --format='{{index .RepoDigests 0}}' siege/example-banner:latest
# → siege/example-banner@sha256:abcdef...
```

Take the `sha256:abcdef...` portion and paste into
`container.digest` in the manifest. The launcher refuses
launches without a digest (CLAUDE.md §3 / Phase 9 hardening) so
players don't get a different image than the author shipped.

## Authoring checklist

Before opening a PR (or submitting to your operator):

- [ ] Manifest validates against the JSON Schema (your IDE
      tells you, since we ship `yaml-language-server` schema
      hints at the top of every example).
- [ ] `make test-challenges` walks through cleanly.
- [ ] At least one `pass` and one `fail` case per flag.
- [ ] Image digest pinned in `container.digest`.
- [ ] Hints, if any, have explicit `cost` values.
- [ ] `egress_allowlist` is the minimum set the challenge
      actually needs. Each entry is a public FQDN, lowercased.
- [ ] Description is markdown and renders cleanly in the
      catalogue (test on a local `make dev`).

## Special-case guides

- **LLM honeypot challenges** — see
  `docs/adr/0001-ai-honeypot-category.md` and
  `docs/runbooks/llm-honeypot-operator.md`. Reference
  implementation:
  `examples/challenges/llm-customer-pii/`.

- **Multi-flag challenges** — give each flag a stable
  `flag_id`. The frontend renders one chip per flag in the
  challenge progress strip. Set `min_matches` on `llm_signal`
  / `multi_part` carefully so partial captures award partial
  credit.

- **Blue-team / detection challenges** — use the `sigma_rule`
  / `yara_rule` / `chain_of_custody` types. Stage your fixture
  event log under `artifacts/` and reference it from
  `events_filename` in the flag config.

## Where to look in the codebase

| What | Where |
|---|---|
| Validator plugins (built-in) | `backend/app/validators/` |
| Validator-registry entry-points | `backend/pyproject.toml` |
| Manifest schema | `packages/bluerange-spec/src/bluerange_spec/` |
| Example challenges | `examples/challenges/` |
| Test harness | `backend/app/services/test_harness/` |
| Loader (manifest → DB rows) | `backend/app/services/challenge_loader/` |

## Getting your challenge live

1. PR (or copy) the directory into your operator's challenge
   tree.
2. Operator runs `make seed` (or POSTs to
   `/api/v1/admin/seed`).
3. Operator opens **Admin → Challenges** in the UI and clicks
   the green Release button next to your slug.
4. `WS_manager` broadcasts `{type: "challenge_released"}` to
   every connected client; the catalogue updates live.
