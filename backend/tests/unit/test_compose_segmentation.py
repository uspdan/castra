"""Compose-config segmentation gate (audit finding R26).

The reference deployment exposes the docker-proxy on plaintext TCP
inside the ``siege-backend`` network and relies on the network being
``internal: true`` plus the membership being limited to the
platform's own services. This test locks that posture so future
edits don't quietly expand the trust boundary.

Failing this test is a security regression: if a new service is
added to ``siege-backend`` or the network stops being internal,
the docker-proxy's plaintext socket starts being reachable from
that surface.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


_REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def compose() -> dict:
    with (_REPO_ROOT / "docker-compose.yml").open() as fh:
        return yaml.safe_load(fh)


class TestSegmentation:
    def test_siege_backend_is_internal(self, compose):
        networks = compose["networks"]
        be = networks.get("siege-backend")
        assert be is not None, "siege-backend network must exist"
        assert be.get("internal") is True, (
            "siege-backend must stay ``internal: true`` — the "
            "docker-proxy listens plaintext on this network and "
            "relies on it being isolated from external traffic"
        )

    def test_siege_challenges_is_internal(self, compose):
        networks = compose["networks"]
        ch = networks.get("siege-challenges")
        assert ch is not None
        assert ch.get("internal") is True, (
            "siege-challenges must stay ``internal: true`` — the "
            "orchestrator (DinD) hosts privileged containers on it"
        )

    def test_docker_proxy_has_no_host_port(self, compose):
        proxy = compose["services"].get("docker-proxy")
        assert proxy is not None
        ports = proxy.get("ports", [])
        assert ports == [], (
            f"docker-proxy must not publish host ports; got {ports!r}. "
            "The plaintext 2375 listener is internal-only by design."
        )

    def test_siege_backend_membership_locked(self, compose):
        """The plaintext docker-proxy socket sits on this network;
        every new member is a new path into the orchestrator. Lock
        the set so additions require an explicit test bump + audit
        re-run."""

        expected = {
            "api",
            "db",
            "redis",
            "docker-proxy",
        }
        actual: set[str] = set()
        for svc_name, svc_def in compose["services"].items():
            nets = svc_def.get("networks") or []
            if "siege-backend" in nets:
                actual.add(svc_name)
        assert actual == expected, (
            f"siege-backend membership drift: expected {expected}, "
            f"got {actual}. Adding a service to siege-backend means "
            "it can dial the docker-proxy; review R26 in the audit "
            "register before relaxing this test."
        )

    def test_docker_proxy_acl_locked(self, compose):
        """tecnativa/docker-socket-proxy is default-deny on every
        verb; the ACL must stay tight. POST=1 covers create/run/exec
        which is what the launcher needs; widening to AUTH, BUILD,
        COMMIT, DISTRIBUTION, or SYSTEM is a security event."""

        proxy = compose["services"]["docker-proxy"]
        env = proxy.get("environment") or []
        env_set = set(env) if isinstance(env, list) else set(
            f"{k}={v}" for k, v in env.items()
        )
        forbidden = {
            "AUTH=1",
            "BUILD=1",
            "COMMIT=1",
            "CONFIGS=1",
            "DISTRIBUTION=1",
            "EXEC=1",
            "GRPC=1",
            "NODES=1",
            "PLUGINS=1",
            "SECRETS=1",
            "SERVICES=1",
            "SESSION=1",
            "SWARM=1",
            "SYSTEM=1",
            "TASKS=1",
        }
        violations = env_set & forbidden
        assert violations == set(), (
            f"docker-proxy ACL widened beyond the audit baseline: "
            f"{sorted(violations)}. Each of these unlocks orchestrator "
            "surface; review R26 before keeping them."
        )

    def test_orchestrator_not_on_siege_backend(self, compose):
        """The orchestrator (privileged DinD) must NOT share a
        network with the api. The api reaches it only through
        docker-proxy, which is the policy enforcement point."""

        orch = compose["services"]["orchestrator"]
        nets = set(orch.get("networks") or [])
        assert "siege-backend" not in nets, (
            "orchestrator must not be on siege-backend — that would "
            "let the api bypass the docker-proxy ACL"
        )
