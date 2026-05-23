# ADR 0001 — Orchestrator socket trust boundary

_Date: 2026-05-23. Audit finding: R26._

## Context

The orchestrator runs Docker-in-Docker (privileged) so it can launch
challenge containers in isolation from the host. The platform's
``api`` service needs to drive that orchestrator — to create
networks, launch / stop containers, inspect state. Two design
choices are available:

1. Direct: ``api`` talks to the orchestrator's daemon socket.
2. Mediated: ``api`` talks to a proxy that enforces an ACL and
   forwards only the verbs the platform needs.

The current deployment uses option (2). The proxy
(``tecnativa/docker-socket-proxy``) listens on plaintext TCP 2375
inside an isolated docker network (``siege-backend``,
``internal: true``). The proxy is the policy enforcement point;
its ACL is enumerated in ``docker-compose.yml`` (``CONTAINERS=1``,
``NETWORKS=1``, ``IMAGES=1``, ``VOLUMES=1``, ``INFO=1``,
``PING=1``, ``VERSION=1``, ``POST=1``).

## Decision

Keep the plaintext-on-internal-network architecture. Do **not**
introduce mTLS to the orchestrator at this time.

### Reasoning

The audit finding R26 (Medium) recommended "switch to mTLS if
reachable from a wider trust boundary." The reachability is
specifically:

* The TCP listener is on ``siege-backend``. That network is
  ``internal: true`` — no internet egress, no host port mapping.
* Only four services are on ``siege-backend``: ``api``, ``db``,
  ``redis``, ``docker-proxy``. None of them initiate connections
  to ``docker-proxy`` *except* ``api``.
* The privileged orchestrator (DinD) is on ``siege-challenges``,
  not on ``siege-backend`` — ``api`` cannot reach it directly,
  only through the policy-enforcing proxy.

In that topology, TLS would defend against an attacker who already
had network sniffing capability on ``siege-backend``. Reaching
that vantage requires:

* Container escape from ``api`` (the only legitimate caller) — at
  which point TLS doesn't matter, the attacker is the legitimate
  caller.
* Host root — at which point TLS doesn't matter, the attacker can
  read every cert.

Both of those require capability levels where this control adds
nothing. mTLS would add operational complexity (cert rotation,
revocation, mounting CA bundles) without changing the threat model.

### Mitigations preserved without mTLS

* ``backend/tests/unit/test_compose_segmentation.py`` locks the
  topology: ``siege-backend`` membership, network ``internal: true``
  flag, absence of host-port mapping on the proxy, and the proxy's
  ACL. Any drift fails CI.
* The proxy ACL is default-deny on every verb we don't enumerate
  (``EXEC``, ``BUILD``, ``COMMIT``, ``SYSTEM``, etc.). Widening
  the ACL is the more likely security regression and the test
  catches it.

## Consequences

* R26 status: documented + gated, not "fixed" via mTLS. If a future
  topology change adds an operator-facing service to
  ``siege-backend`` (eg. a monitoring agent run by a different
  party), the segmentation test will fail and force a re-run of
  this ADR.
* Unix-socket alternative remains available for a future hardening
  pass — would replace the TCP listener entirely.
