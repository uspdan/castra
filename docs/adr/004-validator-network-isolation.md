# ADR 004 — Network isolation for subprocess validators

- **Status**: Accepted
- **Date**: 2026-07-25
- **Closes**: audit finding R19 (validator sandbox escape coverage)

## Context

Validators declaring `requires_subprocess = True` (the YARA and Sigma
plugins, plus any author-supplied validator) run in a forked Python
child spawned by `app.services.validator_sandbox.run_validator_subprocess`.

That child was sandboxed with `resource.setrlimit` only: CPU, address
space, process count, file size and file descriptors were bounded, and
the environment was scrubbed of `SECRET_KEY`, `DATABASE_URL` and cloud
credentials. Nothing bounded the network. A validator could open an
`AF_INET` socket and:

- exfiltrate anything it could read — challenge artefacts, the
  submission, whatever the process' filesystem view exposes;
- pivot into the backend network (Redis, Postgres, the docker-socket
  proxy) using the API container as the origin, which is an SSRF
  surface with no HTTP layer in front of it to filter.

Validator code is author-supplied rather than player-supplied, so this
is a semi-trusted boundary, not a hostile one. It is still the wrong
side of the boundary for a platform whose entire premise is running
untrusted-ish content.

The gap was previously documented by an `xfail` test
(`test_blocks_outbound_socket`) rather than closed.

## Decision

The child installs a **seccomp-BPF filter** — `app/security/syscall_filter.py`
— immediately after applying rlimits and scrubbing the environment, and
crucially **before importing the validator module**, so module-level code
in a hostile plugin is already contained.

The filter denies `socket(2)` for `AF_INET`, `AF_INET6` and `AF_PACKET`
with `EPERM`. `AF_UNIX` remains permitted.

### Why not a network namespace

`unshare(CLONE_NEWUSER | CLONE_NEWNET)` is the more obvious answer and
gives a stronger property (no route to anywhere, not merely no socket).
It works on the host but returns `EPERM` inside the API container:
Docker's default seccomp profile blocks `unshare` with `CLONE_NEWUSER`.

Enabling it would mean granting the API container a wider syscall
surface — or `CAP_SYS_ADMIN` — in order to constrain a child process.
That trades a large boundary for a small one. `prctl(PR_SET_SECCOMP)`
requires no privilege beyond `PR_SET_NO_NEW_PRIVS`, is permitted by
Docker's default profile, and was verified working both on the host and
inside `seige-range-api:latest`.

### Why AF_UNIX stays open

CPython's asyncio event loop builds its self-pipe from `socketpair(2)`.
Denying `AF_UNIX` breaks the runner before the validator executes. No
unix socket is mounted into the API container for a plugin to reach —
the docker socket is proxied over TCP, which the filter blocks.

### Fail-closed

`VALIDATOR_REQUIRE_NETWORK_ISOLATION` defaults to `true`. When the
filter cannot be installed — unknown architecture, kernel refusal — the
child returns an `error: "sandbox"` envelope and the parent raises
`ValidatorError` **without running the validator**. Operators on a host
that cannot install the filter may set the flag to `false`, which
accepts the exfiltration and SSRF risk above in exchange for the
validator running at all.

`_require_network_isolation()` also returns `True` if config lookup
raises, so a broken config is not a route to an open sandbox.

## Consequences

**Positive**

- `test_blocks_outbound_socket` is now a real passing assertion, joined
  by IPv6 and DNS-resolution cases and an `AF_UNIX` negative control.
- The filter is verified by interpreting the BPF program against
  synthetic `seccomp_data` for both supported architectures, so jump
  arithmetic is covered on hosts that cannot execute the other ABI.

**Negative**

- Architecture-specific: `x86_64` and `aarch64` have syscall mappings.
  Anything else fails closed and needs a table entry.
- A validator that legitimately needs network access (none today) can
  no longer have one without an explicit design change. This is
  intended.
- The filter denies socket *creation*, not reachability. A future move
  to rootless Podman or a dedicated sandbox host should revisit the
  network-namespace approach, which is the stronger property.

## Verification

```
$ docker run --rm --entrypoint python seige-range-api:latest /tmp/bpftest.py
filter installed
  AF_INET: blocked (PermissionError 1)
  AF_INET6: blocked (PermissionError 1)
  AF_UNIX socketpair: allowed (needed by runtime)
  asyncio.run works under filter
  DNS: blocked (gaierror)
  file read: e954412fe54e (fs intact)
```
