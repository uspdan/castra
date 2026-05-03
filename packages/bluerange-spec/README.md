# bluerange-spec

Challenge manifest schema (v1) for the seige-range / bluerange platform.

This package defines the on-disk format authors use to publish challenges:

- Pydantic v2 models for validation and IDE support.
- JSON Schema files (drafted from the same models) for tooling and editors.
- Canonical hashing for `manifest_sha256` so the platform can detect drift.

`bluerange_spec` is a one-way dependency: it does **not** import from the
platform's `app/` package. The platform imports from it.

## Layout

```
src/bluerange_spec/
├── __init__.py        # Public exports
├── manifest.py        # ChallengeManifest (top-level v1 model)
├── flag.py            # Flag definitions (typed for the validator registry)
├── artifact.py        # Artifact (path + sha256)
├── hint.py            # Hint (text + cost)
├── author.py          # Author identity
├── container.py       # Container image / port / digest
├── tests.py           # Test cases (Phase 11 harness)
├── canonical.py       # Canonical JSON + SHA-256 hashing
├── load.py            # YAML/JSON manifest loaders
└── schemas/           # JSON Schema documents (kept in sync with models)
```

## Usage (platform code)

```python
from bluerange_spec import load_manifest, ChallengeManifest, manifest_sha256

manifest, raw = load_manifest("examples/challenges/soc-001-off-hours-admin")
digest = manifest_sha256(raw)
```

## Usage (challenge authors)

A challenge directory contains:

```
my-challenge/
├── manifest.yaml
└── artifacts/
    └── ...
```

See `docs/challenge-spec-v1.md` in the repo root for the full reference.
