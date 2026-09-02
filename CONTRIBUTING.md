# Contributing to Castra

Thanks for helping build the range. Pilot feedback, bug reports, challenge
content, and code are all welcome.

## Ground rules

- Be direct and kind. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Security issues go through [private reporting](SECURITY.md), never issues.
- By contributing you agree your contribution is licensed under the
  repository's [BUSL-1.1 license](LICENSE) (and its scheduled Apache-2.0
  change license) — inbound = outbound.

## Dev setup

```bash
git clone https://github.com/uspdan/castra.git
cd castra
cp .env.example .env      # set SECRET_KEY + ADMIN_PASSWORD (see README)
make dev                  # full stack on http://localhost:3000
make seed                 # example challenges
```

Day-to-day targets:

| Command | What |
|---|---|
| `make test` | Backend + spec-package test suites |
| `make test-challenges` | Challenge harness against `examples/challenges/` |
| `make lint` / `make typecheck` | ruff + eslint / mypy + tsc — zero warnings policy |
| `make health` | Probe a running stack |

## Making changes

1. Branch from `main`: `feat/…`, `fix/…`, `docs/…`, `security/…`.
2. Conventional commits: `type(scope): description`.
3. Every behaviour change ships with tests (happy path, error path, edge
   case) and a `CHANGELOG.md` entry under **Unreleased**.
4. CI must be green — the same checks run locally via the targets above.
5. Open a PR against `main`; it is squash-merged after review.
   Security-sensitive changes (auth, crypto, validation, dependencies) get
   an extra-careful review pass — expect questions.

Engineering standards live in [CLAUDE.md](CLAUDE.md) — module boundaries,
error handling, migrations, observability. Match what's already there.

## Contributing challenges

The fastest way in — no platform knowledge needed:

```bash
pip install ./packages/castra-spec
castra new my-challenge && cd my-challenge
# edit challenge.yaml + artifacts
castra validate . && castra test .
```

See the [author handbook](docs/author-handbook.md) for manifest anatomy,
container profiles, and the authoring checklist. Never commit cleartext
flags or answers — CI's `flag-leak` gate will reject them; use the sealing
scripts under `scripts/`.
