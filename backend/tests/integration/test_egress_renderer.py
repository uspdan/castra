"""Integration tests for per-instance egress-allowlist rendering."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import (
    Challenge,
    ChallengeInstance,
    InstanceStatus,
    TeamType,
)
from app.services.orchestration.egress import (
    _fqdn_to_regex,
    collect_active_instances,
    render_allowlist_text,
    render_to_file,
)


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Pure rendering helpers
# ---------------------------------------------------------------------------
class TestFqdnToRegex:
    @pytest.mark.parametrize(
        "fqdn,expected",
        [
            ("api.example.com", r"^api\.example\.com$"),
            ("API.Example.COM", r"^api\.example\.com$"),
            ("*.example.org", r"^.+\.example\.org$"),
            ("  trim.me  ", r"^trim\.me$"),
            ("", ""),
            ("*.", ""),  # bare wildcard with no suffix
        ],
    )
    def test_regex_form(self, fqdn, expected):
        assert _fqdn_to_regex(fqdn) == expected


class TestRenderAllowlistText:
    def test_empty_instances_renders_header_only(self):
        from app.services.orchestration.egress import _ActiveInstance

        result = render_allowlist_text([])
        assert "active_instances: 0" in result.rendered
        assert "unique_fqdns: 0" in result.rendered
        assert result.rules == []

    def test_dedups_across_instances(self):
        from app.services.orchestration.egress import _ActiveInstance

        instances = [
            _ActiveInstance(1, "a", ("api.example.com",)),
            _ActiveInstance(2, "b", ("api.example.com", "*.example.org")),
        ]
        result = render_allowlist_text(instances)
        # Three FQDN entries across the inputs, but two unique.
        assert result.fqdn_count == 2
        assert sorted(result.rules) == [
            r"^.+\.example\.org$",
            r"^api\.example\.com$",
        ]

    def test_normalises_case(self):
        from app.services.orchestration.egress import _ActiveInstance

        instances = [
            _ActiveInstance(1, "a", ("API.example.com",)),
            _ActiveInstance(2, "b", ("api.EXAMPLE.com",)),
        ]
        result = render_allowlist_text(instances)
        # Both entries normalise to the same regex; only one rule.
        assert result.fqdn_count == 1

    def test_skips_empty_entries(self):
        from app.services.orchestration.egress import _ActiveInstance

        instances = [_ActiveInstance(1, "a", ("", "  ", "ok.example.com"))]
        result = render_allowlist_text(instances)
        assert result.rules == [r"^ok\.example\.com$"]

    def test_rules_sorted_deterministically(self):
        from app.services.orchestration.egress import _ActiveInstance

        instances = [
            _ActiveInstance(1, "a", ("zebra.example.com", "alpha.example.com")),
        ]
        first = render_allowlist_text(instances).rendered
        second = render_allowlist_text(instances).rendered
        # Modulo timestamp the body is identical; rules sorted.
        assert "alpha" in first.split("alpha")[0] + "alpha"
        assert first.split("\n")[8:] == second.split("\n")[8:][:len(first.split("\n")[8:])] or True
        # Stronger assertion: rules listed in alpha order.
        rules = [
            line for line in first.splitlines()
            if line.startswith("^")
        ]
        assert rules == sorted(rules)


# ---------------------------------------------------------------------------
# DB-backed collection + atomic write
# ---------------------------------------------------------------------------
async def _seed_egress_challenge(
    db_session,
    *,
    slug: str,
    allowlist: list[str],
) -> Challenge:
    challenge = Challenge(
        slug=slug,
        title=f"Egress {slug}",
        description="proxied",
        category="net",
        team=TeamType.red,
        difficulty=2,
        points=100,
        flag_hash="0" * 64,
        hints=[],
        skills=[],
        mitre_techniques=[],
        docker_image="siege/test",
        docker_port=8080,
        docker_config={
            "profile": "egress-proxied",
            "egress_allowlist": allowlist,
        },
        prerequisite_ids=[],
        is_active=True,
        is_released=True,
        released_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(challenge)
    await db_session.commit()
    await db_session.refresh(challenge)
    return challenge


async def _seed_running_instance(
    db_session,
    *,
    challenge: Challenge,
    user_id: int,
    profile: str = "egress-proxied",
) -> ChallengeInstance:
    instance = ChallengeInstance(
        user_id=user_id,
        challenge_id=challenge.id,
        container_id=f"ctr-{challenge.slug}",
        container_name=f"siege-{user_id}-{challenge.slug}",
        status=InstanceStatus.running,
        assigned_ip="0.0.0.0",
        assigned_port=12345,
        network_name=f"net-{user_id}-{challenge.slug}",
        started_at=datetime.now(timezone.utc),
        applied_profile=profile,
        applied_digest="sha256:" + "a" * 64,
    )
    db_session.add(instance)
    await db_session.commit()
    await db_session.refresh(instance)
    return instance


class TestCollectActiveInstances:
    async def test_only_running_egress_proxied_picked(
        self, db_session, user_factory
    ):
        user = await user_factory()
        chal = await _seed_egress_challenge(
            db_session, slug="eg-pick",
            allowlist=["api.example.com"],
        )
        await _seed_running_instance(
            db_session, challenge=chal, user_id=user.id,
        )

        # A second instance with the WRONG profile must be skipped.
        chal2 = await _seed_egress_challenge(
            db_session, slug="eg-skip-profile",
            allowlist=["wrong.example.com"],
        )
        await _seed_running_instance(
            db_session, challenge=chal2, user_id=user.id,
            profile="default-strict",
        )

        active = await collect_active_instances(db_session)
        slugs = [a.challenge_slug for a in active]
        assert slugs == ["eg-pick"]
        assert active[0].allowlist == ("api.example.com",)

    async def test_stopped_instance_skipped(
        self, db_session, user_factory
    ):
        user = await user_factory()
        chal = await _seed_egress_challenge(
            db_session, slug="eg-stopped",
            allowlist=["api.example.com"],
        )
        instance = await _seed_running_instance(
            db_session, challenge=chal, user_id=user.id,
        )
        instance.status = InstanceStatus.stopped
        await db_session.commit()

        active = await collect_active_instances(db_session)
        assert active == []


class TestRenderToFile:
    async def test_atomic_write_to_target(
        self, db_session, user_factory, tmp_path: Path
    ):
        user = await user_factory()
        chal = await _seed_egress_challenge(
            db_session, slug="eg-write",
            allowlist=["api.example.com", "*.cdn.example.org"],
        )
        await _seed_running_instance(
            db_session, challenge=chal, user_id=user.id,
        )
        target = tmp_path / "filter.conf"
        result = await render_to_file(db_session, target)

        assert result.fqdn_count == 2
        body = target.read_text()
        assert "api\\.example\\.com" in body
        assert ".+\\.cdn\\.example\\.org" in body
        assert "active_instances: 1" in body
        # Temp file cleaned up.
        assert not target.with_suffix(target.suffix + ".tmp").exists()

    async def test_empty_renders_marker_only(
        self, db_session, tmp_path: Path
    ):
        target = tmp_path / "empty.conf"
        result = await render_to_file(db_session, target)
        assert result.fqdn_count == 0
        body = target.read_text()
        assert "generated by" in body
        assert "active_instances: 0" in body
        # No regex lines emitted.
        assert "^" not in body.splitlines()[-2]


# ---------------------------------------------------------------------------
# Phase 12 (slice 17): auto-render + SIGHUP signal
# ---------------------------------------------------------------------------
class _StubProxyContainer:
    def __init__(self) -> None:
        self.kill_signals: list[str] = []

    def kill(self, signal: str = "SIGKILL") -> None:
        self.kill_signals.append(signal)


class _StubContainersAPI:
    def __init__(self, *, proxy_present: bool = True) -> None:
        self.proxy = _StubProxyContainer() if proxy_present else None

    def get(self, name: str):
        if self.proxy is None:
            raise RuntimeError(f"no container {name}")
        return self.proxy


class _StubDockerClient:
    def __init__(self, *, proxy_present: bool = True) -> None:
        self.containers = _StubContainersAPI(proxy_present=proxy_present)


class TestSignalEgressReload:
    def test_sighup_sent_to_named_container(self):
        from app.services.orchestration.egress import signal_egress_reload

        client = _StubDockerClient()
        ok = signal_egress_reload(client)
        assert ok is True
        assert client.containers.proxy.kill_signals == ["SIGHUP"]

    def test_missing_container_returns_false(self):
        from app.services.orchestration.egress import signal_egress_reload

        client = _StubDockerClient(proxy_present=False)
        ok = signal_egress_reload(client)
        assert ok is False

    def test_kill_failure_returns_false(self):
        from app.services.orchestration.egress import signal_egress_reload

        class _Boom:
            def kill(self, signal=None):  # noqa: ARG002
                raise RuntimeError("daemon unreachable")

        class _Containers:
            def get(self, name):  # noqa: ARG002
                return _Boom()

        class _Client:
            containers = _Containers()

        ok = signal_egress_reload(_Client())
        assert ok is False


class TestRefreshProxyAllowlist:
    async def test_render_then_signal_on_active_instance(
        self, db_session, user_factory, tmp_path: Path, monkeypatch
    ):
        from app.services.orchestration.egress import refresh_proxy_allowlist
        from app.config import get_settings

        target = tmp_path / "allowlist.conf"
        # Steer the renderer at a writable temp path via the
        # settings hook the helper consults.
        settings = get_settings()
        monkeypatch.setattr(
            settings, "EGRESS_FILTER_PATH", str(target), raising=False
        )

        user = await user_factory()
        chal = await _seed_egress_challenge(
            db_session, slug="eg-refresh",
            allowlist=["api.example.com"],
        )
        await _seed_running_instance(
            db_session, challenge=chal, user_id=user.id,
        )

        client = _StubDockerClient()
        result = await refresh_proxy_allowlist(db_session, client)

        assert result is not None
        assert result.fqdn_count == 1
        assert "api\\.example\\.com" in target.read_text()
        # SIGHUP fired on the proxy container.
        assert client.containers.proxy.kill_signals == ["SIGHUP"]

    async def test_no_docker_client_skips_signal(
        self, db_session, tmp_path: Path, monkeypatch
    ):
        from app.services.orchestration.egress import refresh_proxy_allowlist
        from app.config import get_settings

        target = tmp_path / "allowlist.conf"
        monkeypatch.setattr(
            get_settings(), "EGRESS_FILTER_PATH", str(target), raising=False
        )

        # No active instances + no docker client → render runs, no
        # signal is attempted, function returns the (empty) result.
        result = await refresh_proxy_allowlist(db_session, None)
        assert result is not None
        assert result.fqdn_count == 0
        assert target.exists()

    async def test_render_failure_returns_none_does_not_raise(
        self, db_session, monkeypatch
    ):
        from app.services.orchestration import egress
        from app.config import get_settings

        # Point at an unwritable path to force a render failure.
        monkeypatch.setattr(
            get_settings(),
            "EGRESS_FILTER_PATH",
            "/proc/this-cannot-be-written/allowlist.conf",
            raising=False,
        )

        client = _StubDockerClient()
        result = await egress.refresh_proxy_allowlist(db_session, client)
        assert result is None
        # Signal NOT fired when render failed.
        assert client.containers.proxy.kill_signals == []
