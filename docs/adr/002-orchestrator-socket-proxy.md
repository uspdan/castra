# ADR 002: Orchestrator Hardening — Socket Proxy + Profile Registry

* **Status**: Accepted
* **Date**: 2026-05-02
* **Phase**: 9 of the 12-phase hardening programme
* **Supersedes**: pre-Phase-9 orchestrator wiring

## Context

The pre-Phase-9 orchestrator was the platform's largest unmitigated
risk. Specifically:

* **DinD over plaintext TCP 2375.** `DOCKER_TLS_CERTDIR=""` was set on
  the orchestrator service, exposing the Docker daemon over the
  internal `siege-backend` bridge with no TLS, no client auth, and no
  ACL. Any process on that network could create privileged containers.
* **Hardcoded launch flags.** `services/orchestrator.py:launch_instance`
  set `read_only=True`, `cap_drop=ALL`, `no-new-privileges`, and
  resource limits in 116 lines of imperative code. There was no
  notion of a profile, no seccomp, no apparmor, no digest pinning,
  and no refusal layer — a future code change relaxing any of these
  flags would not have been visible at the manifest layer.
* **No image digest enforcement.** Manifests could declare
  `image: alpine:3.19` without pinning a digest; an upstream-registry
  tag swap would replace the image content under us silently.
* **`DOCKER_HOST` mismatch** — `config.py` claimed `:2376` (TLS) but
  the env override landed on `:2375` (plaintext). The plaintext won;
  the config file was misleading.

CLAUDE.md §3 mandates least-privilege and validated boundaries; the
orchestrator did not meet that bar.

## Decision

We adopted three coupled changes:

### 1. `tecnativa/docker-socket-proxy` between api and DinD

A new `docker-proxy` service runs alongside DinD and the api. It
mounts the daemon's Unix socket via a shared `docker_socket` named
volume and exposes plaintext TCP 2375 on the internal `siege-backend`
network. Only `CONTAINERS`, `NETWORKS`, `IMAGES` (plus baseline
`INFO/PING/VERSION`) are enabled; everything else returns 403.

DinD now runs with `DOCKER_TLS_CERTDIR=/certs`. Its TCP listener is
TLS-only, but no port is published — the proxy's Unix-socket reach
is the only network entrypoint. The TLS listener is defense-in-depth
in case a future deployment misconfigures the network topology.

### 2. Container profile registry + refusal layer

`app/services/orchestration/profiles.py` defines three frozen
profiles — `default-strict`, `malware-sandbox`, `egress-proxied` —
with all security-critical fields baked in (mem, cpu, pids, tmpfs,
TTL ceiling, network mode, caps, security-opt, seccomp profile name).
Manifests select a profile by name; the launcher composes its
docker-py kwargs purely from the profile and runs
`enforce_no_forbidden(...)` as a backstop. Adding a profile requires
a code change.

### 3. Mandatory image digest pinning at launch

`Container.digest` already existed in the manifest spec. Phase 9
makes it required at launch (loader logs a warning; launcher refuses).
The image is run as `image@digest`, not `image:tag`.

## Alternatives considered

* **Replace DinD with rootless Podman.** Removes the largest
  remaining cap — privileged: true. Rejected for Phase 9 because:
  (a) it forces a docker-py-to-podman-api migration, (b) the test
  story for podman-in-CI is weaker, and (c) it changes the operator
  story (most users know Docker, not Podman). Captured as future
  direction in `docs/security-model.md`.
* **Fronting DinD with a TLS-aware reverse proxy** (e.g. nginx with
  `ssl_verify_client on` upstream → DinD on :2376). Rejected because
  tecnativa's path-allowlisting is well-tested and a hand-rolled
  nginx ACL on Docker REST paths is fragile (path semantics change
  between API versions).
* **Profiles as DB rows.** Considered storing profile parameters in
  Postgres so operators could tune them without redeploying.
  Rejected: the security envelope is the security-critical surface;
  changing it should require a code review and an ADR, not an admin
  UI click.

## Consequences

### Positive

* The api never speaks to a privileged daemon directly.
* A future security-relevant change to the launcher must touch
  `profiles.py` (frozen dataclasses) — visible at code review.
* The `Container.digest` field is now load-bearing; un-pinned
  challenges are non-launchable.
* Audit ledger records the profile name and digest per launch; the
  instance row records the seccomp-bytes hash — auditors can prove
  which policy was running.

### Negative

* **DinD remains `privileged: true`.** The cost of nesting; the
  proxy doesn't change that. Rootless Podman is the path to remove
  it, and it's deferred.
* **Egress-proxy adds operational surface.** A new compose service
  (`egress-proxy`) and a new bridge network (`siege-egress`).
  Operators must understand the allowlist file. Documented in
  `docs/security-model.md`.
* **Per-instance allowlist rendering not yet wired.** The manifest's
  `egress_allowlist` field is captured and persisted but the
  tinyproxy `Filter` directive consumes only a deployment-wide static
  file. A Phase-9 follow-up renders per-instance filters.
* **`docker==7.1.0` upgrade** drops the test-only `urllib3<2`/
  `requests<2.32` workaround pins. CI runners must support modern
  urllib3.
* **Image-digest enforcement breaks any pre-Phase-9 manifest** that
  shipped without a digest. Existing example challenges in
  `examples/challenges/` continue to load (with a warning) but
  cannot launch until updated.
