# Challenge Spec — v1

> The on-disk format authors use to publish challenges to seige-range.
> Implemented by the `bluerange-spec` package under
> `packages/bluerange-spec/`. Loaded by
> `backend/app/services/challenge_loader/` and the
> `python -m app.tools.load_challenges` CLI.

This document is the authoritative reference for v1. The
`bluerange_spec.ChallengeManifest` Pydantic model and the frozen
JSON Schema at
`packages/bluerange-spec/src/bluerange_spec/schemas/manifest.schema.json`
are kept in lockstep by an automated parity test
(`tests/test_schema_parity.py`); when this document and the schema
disagree, **the schema wins**.

---

## Layout on disk

A challenge is a directory containing a `manifest.yaml` (or
`manifest.yml`, or `manifest.json`) at its top level, plus any artefact
files referenced from the manifest.

```
my-challenge/
├── manifest.yaml
└── artifacts/
    ├── auth.log
    └── ...
```

Editor support: drop the following line at the top of `manifest.yaml`
to enable yaml-language-server completion + validation against the
frozen schema:

```yaml
# yaml-language-server: $schema=path/to/manifest.schema.json
```

---

## Top-level fields

| Field | Type | Required | Notes |
|---|---|:-:|---|
| `spec_version` | string `"1"` | ✓ | Locks the manifest to v1. |
| `slug` | string | ✓ | 1–100 chars, `[a-z0-9-]`, must start/end with alnum. Globally unique across loaded challenges. |
| `title` | string | ✓ | Display name. |
| `description` | string | ✓ | Markdown-friendly prose, ≤10 KB. |
| `team` | enum | ✓ | `red`, `blue`, or `purple`. |
| `category` | string | ✓ | Free-text category label (`SOC`, `DFIR`, `Web`, …). |
| `difficulty` | integer 1–5 | ✓ | 1 = easy, 5 = brutal. |
| `points` | integer 1–100 000 | ✓ | Base score for solving the challenge end-to-end. |
| `license` | string | ✓ | SPDX identifier or named licence (`MIT`, `CC-BY-4.0`, etc). |
| `author` | object | ✓ | See [Author](#author). |
| `container` | object | ✓ | See [Container](#container). |
| `flags` | array | ✓ | At least one. See [Flags](#flags). |
| `hints` | array | – | See [Hints](#hints). |
| `artifacts` | array | – | See [Artifacts](#artifacts). |
| `skills` | array of strings | – | Free-text skill tags (≤20 entries). |
| `mitre_techniques` | array of strings | – | Validated against the `T####[.###]` / `TA####` shape. |
| `prerequisites` | array of slugs | – | Must be other challenges; cannot include self. |
| `tests` | object | – | See [Tests](#tests). |

Unknown top-level fields are rejected (`extra="forbid"`).

### Author

```yaml
author:
  name: "Daniel Hay"
  email: "daniel_hay@example.com"   # optional
  url: "https://github.com/dhay"    # optional
```

`name` is required; either `email` or `url` is recommended so
reviewers can contact the author. Neither is enforced in v1.

### Container

```yaml
container:
  image: "siege/blue-soc-base"
  port: 8080
  digest: "sha256:abc..."   # optional in v1; required by Phase 9
  profile: default-strict   # kebab-case; Phase 9 validates against the
                            # PROFILES set
```

- `image` is a permissive OCI reference (lowercase, optional `:tag`).
  Pin via `digest` rather than encoding the digest into the tag.
- `digest` is `sha256:<64-hex>` when present.
- `profile` defaults to `default-strict`. Phase 9 will reject
  manifests whose profile is not registered.

### Flags

A challenge declares one or more flags. Each flag has a `type`
discriminator naming the validator plugin that will check submissions
against it (Phase 8 introduces the registry). v1 ships three types
out of the box.

```yaml
flags:
  - id: elevation_ts          # 1–64 chars, [a-z0-9_-]
    type: exact
    points: 100
    value: "CTF{REDACTED}"
    case_sensitive: true       # default

  - id: pattern_match
    type: regex
    points: 150
    pattern: "^CTF\\{[a-z0-9_]+\\}$"
    case_sensitive: true

  - id: chained
    type: multi_part
    points: 200
    parts: ["alpha", "bravo"]   # 2–20 entries
    ordered: true
```

Constraints:

- `flags[].id` must be unique within a single challenge.
- `regex.pattern` must compile under Python's `re` module at load time.
- The aggregate of `flags[].points` is what the platform awards on a
  full clear; partial credit is the validator's responsibility.
- Cleartext is stored only for `regex` (the pattern) and `multi_part`
  (the parts list). `exact.value` is stored as a SHA-256 hash; the
  platform never persists the cleartext.

### Hints

```yaml
hints:
  - text: "Filter for `action=elevate`."
    cost: 10
  - text: "The flag is `CTF{REDACTED}`."
    cost: 25
```

`cost` is the points deduction the platform applies when the user
unlocks the hint before solving. `cost: 0` is permitted (free hint).

### Artifacts

```yaml
artifacts:
  - path: "artifacts/auth.log"
    sha256: "cf4f...c63e9868e"
    size_bytes: 1289           # optional but recommended
    description: "..."
```

- `path` is relative to the challenge directory. Absolute paths,
  parent traversal (`..`), and non-`[A-Za-z0-9._\-/]` characters are
  rejected.
- `sha256` must be 64 lowercase hex chars and must match the file's
  on-disk digest at load time. Mismatch fails the load.
- `size_bytes` is informational; the loader does not check it in v1.

### Tests

Phase 11 ships a `bluerange-test` runner that consumes these cases.
v1 only requires the schema to be correct so authors can start writing
tests now.

```yaml
tests:
  cases:
    - name: "correct flag passes"
      flag_id: elevation_ts
      submission: "CTF{REDACTED}"
      expected: pass            # or "fail"
      description: "..."
```

- `flag_id` must reference a flag declared in this manifest. Unknown
  IDs are rejected at load time.

---

## Loading semantics

Run `python -m app.tools.load_challenges --dry-run examples/challenges`
to validate every manifest under a path without touching the database.
Use `--apply` to upsert.

For each discovered manifest:

1. Parse + validate against the v1 schema.
2. Hash the canonical JSON form (`sort_keys=True`, no whitespace) →
   `manifest_sha256`.
3. SHA-256 each declared artefact and compare to the manifest entry.
4. If creating a new challenge or `manifest_sha256` differs from the
   stored value, mark `pending_review=true` and `is_released=false`.
   An operator must re-release through the admin path after reviewing
   the diff.
5. Replace the challenge's flag and artifact rows wholesale (the
   manifest is the source of truth; partial drifts are not supported).

The loader is idempotent: running `--apply` twice in a row against an
unchanged manifest tree leaves every challenge in the `unchanged`
state.

---

## Drift detection

`manifest_sha256` is recomputed from the canonical JSON of the loaded
manifest on every load. Any change — even a comment-free reformat in
YAML, since YAML round-trips through `dict` before hashing — produces
a new digest. The platform uses that to:

- Refuse to silently accept a tampered manifest in production.
- Surface drift in the admin UI as `pending_review`.
- Require an operator to re-release before the challenge becomes
  visible to players.

Authors should treat `manifest_sha256` as opaque; do not include it in
the manifest itself.

---

## Regenerating the JSON Schema

The frozen schema in
`packages/bluerange-spec/src/bluerange_spec/schemas/manifest.schema.json`
is generated from the Pydantic model. After changing the model, run:

```bash
python -c "
import json
from bluerange_spec import ChallengeManifest
s = ChallengeManifest.model_json_schema()
s['\$schema'] = 'https://json-schema.org/draft/2020-12/schema'
s['\$id'] = 'https://seige-range.local/schemas/bluerange-spec/v1/manifest.schema.json'
s['title'] = 'BluerangeChallengeManifest'
s['description'] = 'v1 challenge manifest for the seige-range platform.'
print(json.dumps(s, indent=2, sort_keys=True))
" > packages/bluerange-spec/src/bluerange_spec/schemas/manifest.schema.json
```

The parity test in
`packages/bluerange-spec/tests/test_schema_parity.py` will fail until
this is done.

---

## Migration from the legacy `challenge.json`

The 12 challenges shipped under `challenges/` predate v1 and use a
flat `challenge.json` format with no licence, author, test cases, or
artefact integrity. Per Phase-0 decision (Q2 → option b), these stay
under `challenges/` as legacy and are **ignored by the v1 loader**.
New canonical examples live under `examples/challenges/`.

To convert a legacy challenge to v1:

1. Move the directory to `examples/challenges/` (or wherever
   `--apply` will scan).
2. Author a `manifest.yaml` with the fields above. Pick a sensible
   licence (`CC-BY-4.0`, `MIT`, etc) and fill in `author`.
3. Hash any artefacts referenced from the description and add an
   `artifacts:` block with their `sha256`s.
4. Add at least one test case under `tests.cases`.
5. Run `python -m app.tools.load_challenges --dry-run <path>` until it
   reports `loaded`.

A separate cookiecutter (Phase 11) will generate this scaffold
automatically.
