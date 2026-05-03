# Orchestrator REDACTED Model (Phase 9)

This document describes the security envelope around launched challenge
containers. It complements [ADR 002](adr/002-orchestrator-socket-proxy.md),
which records the architectural decision; this file is the operational
reference.

---

## Threat model

The platform launches user-submitted challenge containers. The base
assumption is that a challenge image — whether built in-house or pulled
from a third-party registry — may contain hostile code. The blue-team
focus narrows the threat: we are not running unknown red-team tooling
against the host, but rather defensive-analysis tooling that may be
buggy, may parse adversarial input, or may be re-purposed in misuse.
The model still defends against:

* Container breakouts via privilege escalation, kernel exploit, or
  socket leakage.
* Lateral movement between concurrent instances.
* Outbound exfiltration from a compromised challenge container.
* Tampering with the audit ledger, the manifest pipeline, or the
  Docker daemon directly.

It does **not** defend against:

* Host kernel zero-days that bypass all userspace mitigations.
* A compromised platform operator (the audit ledger raises the cost
  but does not eliminate it; pair with off-platform append-only sink).

---

## Defense in depth

The orchestrator's security envelope is composed of seven independent
layers; bypassing any one does not bypass the rest.

```
   user ➜ api ➜ docker-socket-proxy ➜ DinD ➜ challenge container
                  │                    │       │
                  │                    │       └─ profile (seccomp + caps + read-only + tmpfs + pids)
                  │                    └─ TLS internal listener
                  └─ ACL: CONTAINERS, NETWORKS, IMAGES only
```

### 1. `tecnativa/docker-socket-proxy`

The api never speaks to the Docker daemon directly. It connects to
`docker-proxy:2375` on the internal `siege-backend` bridge. The proxy
exposes only the `CONTAINERS`, `NETWORKS`, and `IMAGES` API surfaces
plus baseline `INFO/PING/VERSION`. Anything else (volume management,
swarm, plugins, exec into existing containers from other users)
returns 403.

### 2. DinD with TLS-only TCP listener

The orchestrator service runs `docker:24-dind` with
`DOCKER_TLS_CERTDIR=/certs`. Its TCP listener requires TLS, but **no
TCP port is published** — the only network entrypoint is the proxy
above. The proxy reads the daemon socket via the shared
`docker_socket` named volume. The TLS listener is defense-in-depth:
even a misconfigured deployment that exposed DinD's network port
would not accept plaintext traffic.

### 3. Container profile registry

Every launched container is governed by a profile defined in
`app/services/orchestration/profiles.py`. Profiles are constants in
code; manifests can request a profile by name but cannot tune any of
its parameters. The launcher composes its docker-py kwargs purely
from the profile, so manifest-supplied fields on profile-managed
slots are ignored.

| Profile | Use case | Mem | CPU | TTL max | Network | Notes |
|---|---|---|---|---|---|---|
| `default-strict` | Default for blue-team challenges | 512m | 1 core | 7,200s | bridge-isolated | seccomp `default-strict` |
| `malware-sandbox` | Unknown-binary triage | 384m | 0.5 core | 1,800s | bridge-isolated | seccomp `malware-sandbox` (denies `socket`/`socketpair`/`ptrace`/key-mgmt) |
| `egress-proxied` | Challenges needing limited internet | 512m | 1 core | 3,600s | egress-proxied | requires `egress_allowlist` in manifest |

Adding a profile is a code change with an accompanying ADR; it is
not a runtime decision.

### 4. Bundled seccomp profiles

`app/security/seccomp/{default-strict,malware-sandbox}.json` are
loaded at boot via `SeccompProfile.validate_all_profiles()`. The
parser refuses any malformed profile and the api fails fast with a
structured stderr line + `exit(1)` — same shape as Phase 3's secret
fail-fast.

The on-disk profile bytes are SHA-256-summed on launch and persisted
on the `ChallengeInstance` row (`seccomp_profile_sha256`). The audit
ledger record for the launch carries the profile name; the row carries
the bytes-hash. Together they let an auditor prove which seccomp
policy was running, not just which name was claimed.

### 5. Forbidden-fields refusal

The launcher composes the docker-py kwargs from the profile, then
runs `enforce_no_forbidden(...)` as a runtime guard. Refused fields:

* `privileged`
* `network_mode`/`pid_mode`/`ipc_mode`/`userns_mode` set to `host`
* `cap_add` containing any of `SYS_ADMIN`, `SYS_MODULE`, `SYS_PTRACE`,
  `SYS_RAWIO`, `SYS_BOOT`, `NET_ADMIN`, `MAC_ADMIN`, `MAC_OVERRIDE`,
  `DAC_READ_SEARCH`
* `binds` or `volumes_from` (legacy mount syntax)
* `volumes` mapping any path under `/var/run/docker.sock`, `/proc`,
  `/sys`, `/dev`, `/etc`, or `/`

The refusal layer is a backstop, not the primary control: profiles
already exclude these fields. It exists to catch future drift if a
profile is ever extended in a way that would have allowed one of
these.

### 6. Image digest pinning

The launcher refuses to start a container whose manifest does not
declare `container.digest` (a `sha256:<64hex>` reference). The
container is run as `image@digest`, not `image:tag`, so a tag-poisoned
upstream registry cannot replace the image content out from under us.
Manifests without digests load (with a warning) but are non-launchable
until a digest is added.

### 7. Egress proxy (egress-proxied profile only)

The `egress-proxied` profile creates a per-instance bridge with
`internal=true` and connects the `siege-egress-proxy` container to
that bridge. The challenge container has only one route to the
outside world: through tinyproxy on `:8888`, subject to the FQDN
allowlist in `docker/egress-proxy/egress-allowlist.conf`.

`FilterDefaultDeny=Yes` is set, so anything not explicitly allowed is
blocked. CONNECT is restricted to ports 443/8443 (TLS only). The
manifest's `egress_allowlist` field is captured and persisted; runtime
re-rendering of per-instance allowlists is a follow-up item — Phase 9
ships static-allowlist mode at the proxy-service level.

---

## Audit trail

Every launch / stop / reset / expired event is appended to the hash-
chained audit ledger (Phase 2). Phase 9 collapses the audit emit into
the same DB transaction as the `ChallengeInstance` insert — a launch
either commits both the row and the audit, or commits neither.

Per-instance audit payload includes:

* `instance_id`, `user_id`, `challenge_id`
* `applied_profile` (e.g. `default-strict`)
* `applied_digest` (the actual `sha256:<64hex>` pinned)
* `port`, `expires_at`

The instance row separately records `seccomp_profile_sha256` so the
chain can prove which profile-bytes ran for any past instance.

---

## Future direction

* **Rootless Podman** — drop the `privileged: true` flag on DinD by
  switching to user-namespaced rootless Podman as the daemon. This
  removes the largest remaining capability — the cost of nesting —
  but requires a non-trivial migration off docker-py and is out of
  scope for Phase 9.
* **Per-instance egress allowlist rendering** — read
  `Challenge.docker_config["egress_allowlist"]` at launch and render
  a per-instance tinyproxy filter. Today the field is captured and
  persisted but not yet consumed at runtime; a static deployment-wide
  allowlist is the only filter applied.
* **Image pull verification** — verify the digest the local daemon
  resolved matches what the manifest claims, after pull. The current
  launcher passes `image@digest` to docker-py and trusts it. A
  dedicated post-pull `client.images.get()` cross-check would close
  the residual gap.
