# ADR 005 — Artifact-only challenges and per-instance flags

- **Status**: Accepted (part 1 implemented; part 2 MVP implemented
  2026-08-19 — exact flags only)
- **Date**: 2026-08-17
- **Context**: product direction review against generator-style CTF
  platforms (reference: 8gwifi.org/ctf)

## Context

Every challenge currently requires a container. `container:` is a
mandatory manifest field, and the launch path always goes through the
DinD orchestrator — even when the challenge is a bundle of log files
the player reads.

That mismatch is not hypothetical. Of the 62 in-repo challenges:

| Category | Count | Actually needs a runtime? |
|---|---|---|
| Web Exploitation | 20 | yes |
| Network Device Forensics | 19 | mostly (live emulation) |
| Threat Hunting | 15 | **no — static logs** |
| Forensics / Detection Eng / Crypto / Log / IR | 7 | **no** |

Roughly a third of the catalogue spins a privileged-DinD-hosted
container to serve files that never change. Those instances consume
port allocations, TTL-reaper attention, memory ceilings and launch
latency for nothing.

Separately, flags are static per challenge: one value, shared by every
player, baked into the image layer at build time
(`COPY .flag.txt /opt/flag.txt`). That design blocks three things at
once: flag rotation without rebuilding 62 images, any defensible
anti-sharing story for scored use, and publishing challenge images at
all — the image *is* the secret.

## Decision — part 1 (implemented): `container` becomes optional

Spec v1.1 makes `container:` optional. A manifest with no container
must declare at least one artifact — a challenge with neither has no
content, and the spec rejects it.

Artifact-only challenges:

- skip the orchestrator entirely — no instance, no port, no TTL;
- are served by a new authenticated download endpoint,
  `GET /api/v1/challenges/{slug}/artifacts/{path}`;
- render in the UI with a download list where LAUNCH would be.

### Serving is allowlist-only, from a read-only mount

The API gains a read-only mount of the challenges tree
(`CHALLENGES_DIR`, default `/challenges`). Three properties make this
safe to expose:

1. **The DB is the allowlist.** Only paths present in
   `challenge_artifacts` for that released, active challenge are
   servable. The table is populated from the manifest at load time,
   after the loader has verified each file's sha256 on disk. A path not
   in the manifest — including the `.flag.txt` / `.answers.json`
   sidecars staged next to Dockerfiles — is a 404 regardless of whether
   the file exists.
2. **Resolved-path containment.** The requested path is resolved
   (symlinks followed) and must land inside the challenge's directory.
   Traversal and symlink escape both fail closed.
3. **Read-only.** The mount is `:ro`; the API cannot modify the tree.

Rejected alternative: copying artifacts into object storage at load
time. It removes the mount but introduces a second source of truth that
can drift from the sha-verified tree, plus storage lifecycle nobody is
asking for at this scale. Revisit if multi-node API is ever real.

### Why the size cap on hash-at-serve

Artifacts are hash-verified at **load time**, not per request.
`Artifact.size_bytes` permits files up to 10 GiB; hashing per download
would be an easy CPU DoS. The trade-off is that a file corrupted on
disk after load is served as-is. Acceptable: the mount is read-only and
the load-time check catches authoring errors, which is the real risk.

## Decision — part 2 (accepted, deferred): per-instance flags

Direction agreed; not in this change because it touches scoring,
validation, the launcher contract and the CLI at once.

The target model:

- flag value (or per-flag salt) lives on `ChallengeInstance`, minted at
  launch;
- the launcher injects it via environment/tmpfs file at container
  start — the image never contains it;
- validation reads the instance row, not the challenge row;
- artifact-only challenges template the flag into artifacts at download
  time, or (simpler, likely v1) keep static flags until templating is
  designed.

Consequences worth writing down now:

- **Unblocks image publishing.** With no baked flag, challenge images
  stop being secrets — the entire distribution question from the
  packaging discussion reopens on better terms.
- **Kills cross-player flag sharing** for container challenges.
- **Requires a migration window** where both static and per-instance
  flags validate, because 62 existing challenges won't convert at once.
- The SDK's `castra test` must be able to mint ephemeral flags locally,
  so the harness contract grows a flag-provider seam. This is why the
  decision is recorded *before* the SDK extraction: building the CLI
  against the static-flag assumption would bake the old model into the
  public contract.

## Consequences — part 1

Positive: a third of the catalogue becomes instant-launch and
zero-compute; challenges work with the orchestrator down; authors can
ship a pure-forensics challenge with no Docker knowledge at all.

Negative: a new read-only mount into the API container (mitigated as
above); one more branch in the launch path; the spec's "every challenge
has a container" invariant is gone, so downstream consumers of
`docker_image` must handle NULL — enforced by making the columns
nullable and auditing call sites.

Neutral: existing manifests are untouched — `container:` remains valid
and behaves exactly as before. This is spec v1.1, additive only.
