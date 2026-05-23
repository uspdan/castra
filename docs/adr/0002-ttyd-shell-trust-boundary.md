# ADR 0002 — ttyd shell trust boundary

_Date: 2026-05-23. Audit finding: R20._

## Context

Players run the in-browser analyst workstation by hitting
``GET /workstation/launch`` from the platform UI. The launcher
spawns a per-user container (``siege/workstation:latest``) inside
the orchestrator DinD, then nginx reverse-proxies the player's
HTTPS session to the container's :7681 ttyd port. The traffic flow
is:

```
player browser
   │ HTTPS (Cache-Control: private, no-store via R33)
   ▼
nginx ───────► host port 11000+user_id ───────► DinD ───────► workstation:7681
                                                                    │
                                                                    ▼
                                                               ttyd → bash
                                                               (analyst uid)
```

This ADR documents what the trust boundary actually enforces and
which gaps stay open as accepted risk.

## Decision

The workstation container is reachable only via nginx, runs
unprivileged, drops all but the minimum capabilities required to
operate ttyd + sshd, and has ``no-new-privileges`` set.

### Authentication

* ttyd is launched with ``--credential analyst:<password>``. The
  password is a fresh 20-character random ASCII string generated
  per launch (``services/workstation.py::_new_password``).
* The password is emitted *once* — in the API response from
  ``POST /api/v1/workstation/launch`` (``one_shot_password`` field
  on :class:`WorkstationDescriptor`). Subsequent ``GET /status``
  calls intentionally omit it.
* The password is **not** persisted in any DB — only as the
  ``SIEGE_WORKSTATION_PASSWORD`` env var on the running container.
  Stopping the workstation discards it; re-launch generates a new
  one.
* WebSocket upgrade carries the Basic-Auth header over TLS
  (terminated at nginx) — no in-the-clear hop for player auth.

### Container surface

Verified by ``backend/tests/unit/test_workstation_service.py::
test_launch_drops_caps_and_sets_no_new_privileges``:

* ``cap_drop=["ALL"]`` + a minimum cap allow-list of
  ``CHOWN, DAC_OVERRIDE, FOWNER, SETGID, SETUID, NET_BIND_SERVICE, KILL``.
  Adding to this list is a security event the test will surface.
* ``security_opt=["no-new-privileges:true"]`` — refused
  setuid/setgid escalation inside the container.
* ttyd drops to ``analyst`` uid + gid before spawning the shell
  (``entrypoint.sh`` lines 40–47); root is never reachable from
  the player's session.
* ``sudo`` is restricted to ``tcpdump / tshark / nmap`` only
  (``/etc/sudoers.d/analyst-tools``).
* Mounts:
  * ``/home/analyst`` — per-user named volume (rw). The only
    persistent state the player can leave behind.
  * No Docker socket. No host filesystem mounts. No /proc /sys
    bind-mounts.
* Network membership at launch: the orchestrator's default
  network. ``attach_to_network`` is called *separately* by the
  challenge-launch flow to add the workstation to each active
  challenge's per-instance network so the analyst can ``connect
  <slug>`` to the live target.

### Egress

The workstation has internet egress by design — the analyst kit
includes ``apt``, ``pip``, ``curl``, etc. for legitimate research.
Players are authenticated and accept the operator's AUP at signup,
so this is in-band.

## Accepted residual risks

* **ttyd binds 0.0.0.0**. It has to, because nginx reaches it via
  the orchestrator's published host port. Inside the container's
  net-namespace that's only reachable from the docker network the
  orchestrator chose for it. Other challenge containers on the
  same per-instance network *can* reach :7681, but only after
  ``attach_to_network`` has run — at which point they're already
  the analyst's targets, not adversaries.
* **No seccomp profile beyond Docker default**. The default
  profile blocks ~50 high-risk syscalls (keyctl, finit_module,
  etc.); the workstation doesn't need anything tighter for the
  player's analyst kit. A bespoke profile is on the audit
  follow-up list for a future hardening sprint.
* **Password authentication for SSH**. The same one-shot password
  also unlocks SSH on :2222 (orchestrator's published 11100+uid).
  Key-based auth would be stronger but adds a key-distribution
  problem we don't have today. Tracked as a future ADR.
* **No idle timeout on the WebSocket** beyond ttyd's own
  inactivity-disconnect. The platform's reaper (``reap_idle``)
  stops a workstation whose uptime exceeds 8 hours regardless of
  activity.

## Consequences

* R20 closed: the trust boundary is documented, tested for
  capability drift, and the residual risks are explicit. A future
  ``/secure-audit`` run can grade against this ADR.
* The capability allow-list test pins the cap-set; widening it
  requires editing the test, which routes through code review.
