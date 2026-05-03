"""Phase 9 — launcher: profile composition, digest enforcement, refusal."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.orchestration import launcher
from app.services.orchestration.launcher import MissingImageDigest


class _FakeRedis:
    """Async-compatible Redis stub: tracks set/incr/delete calls."""

    def __init__(self) -> None:
        self._values: dict[str, int] = {}
        self.calls: list[tuple] = []

    async def set(self, key, value, nx=False, ex=None):
        self.calls.append(("set", key, value, nx, ex))
        if nx and key in self._values:
            return None
        self._values[key] = value
        return True

    async def incr(self, key):
        self.calls.append(("incr", key))
        self._values[key] = int(self._values.get(key, 9_999)) + 1
        return self._values[key]

    async def delete(self, key):
        self.calls.append(("delete", key))
        self._values.pop(key, None)


class _FakeImage:
    """Stand-in for ``docker.models.images.Image``.

    Only the ``attrs`` dict matters for the launcher's post-pull
    digest verification; we expose ``RepoDigests`` as a configurable
    list so per-test scenarios can simulate a clean match, an empty
    pull (cache miss), or a deliberate mismatch.
    """

    def __init__(self, repo_digests: list[str]):
        self.attrs = {"RepoDigests": list(repo_digests)}


class _FakeContainer:
    def __init__(self, *, image_ref: str | None = None,
                 repo_digests: list[str] | None = None):
        self.id = "ctr-fake"
        # Default: the resolved image's RepoDigests carries the very
        # ref the launcher passed in. Tests that want to simulate
        # mismatch override ``repo_digests`` explicitly.
        if repo_digests is None:
            repo_digests = [image_ref] if image_ref else []
        self.image = _FakeImage(repo_digests)
        self.stop_calls: list = []
        self.remove_calls: list = []

    def stop(self, timeout: int = 0):
        self.stop_calls.append(timeout)

    def remove(self, force: bool = False):
        self.remove_calls.append(force)


class _FakeNetwork:
    def __init__(self, name: str):
        self.name = name


class _FakeContainersAPI:
    def __init__(self, capture: dict, *, repo_digests_override=None):
        self._capture = capture
        self._repo_digests_override = repo_digests_override
        self.last_container: _FakeContainer | None = None

    def run(self, **kwargs):
        self._capture.update(kwargs)
        image_ref = kwargs.get("image")
        repo_digests = (
            self._repo_digests_override
            if self._repo_digests_override is not None
            else None
        )
        self.last_container = _FakeContainer(
            image_ref=image_ref,
            repo_digests=repo_digests,
        )
        return self.last_container


class _FakeRemovableNetwork(_FakeNetwork):
    def remove(self):
        return None


class _FakeNetworksAPI:
    def __init__(self):
        self._created: dict[str, _FakeRemovableNetwork] = {}

    def create(self, name, **kwargs):
        net = _FakeRemovableNetwork(name)
        self._created[name] = net
        return net

    def get(self, name):
        # Return the live network if we created it; otherwise raise
        # the docker-py equivalent of "not found". The launcher's
        # cleanup path only cares that .remove() succeeds.
        if name in self._created:
            return self._created[name]
        raise KeyError(name)


class _FakeDockerClient:
    def __init__(self, *, repo_digests_override=None):
        self.captured_run_kwargs: dict = {}
        self.containers = _FakeContainersAPI(
            self.captured_run_kwargs,
            repo_digests_override=repo_digests_override,
        )
        self.networks = _FakeNetworksAPI()


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> _FakeDockerClient:
    client = _FakeDockerClient()
    monkeypatch.setattr(
        "app.services.orchestration.docker_client.get", lambda: client
    )
    return client


def _make_challenge(*, profile: str = "default-strict", digest: str | None = None):
    config = {"profile": profile}
    if digest is not None:
        config["digest"] = digest
    return SimpleNamespace(
        id=42,
        slug="test-challenge",
        docker_image="siege/test",
        docker_port=8080,
        docker_config=config,
    )


def _make_db():
    db = MagicMock()
    db.execute = AsyncMock()
    # _check_user_caps issues two execute calls; both must look "empty".
    count_result = MagicMock()
    count_result.scalar = MagicMock(return_value=0)
    existing_result = MagicMock()
    existing_result.scalar_one_or_none = MagicMock(return_value=None)
    db.execute.side_effect = [count_result, existing_result]
    db.add = MagicMock()
    db.flush = AsyncMock()

    async def _refresh(instance):
        instance.id = 7
    db.refresh = AsyncMock(side_effect=_refresh)
    return db


@pytest.mark.asyncio
async def test_launch_refuses_without_digest(fake_client) -> None:
    challenge = _make_challenge(digest=None)
    db = _make_db()
    redis = _FakeRedis()
    with pytest.raises(MissingImageDigest):
        await launcher.launch_instance(1, challenge, db, redis)


@pytest.mark.asyncio
async def test_launch_uses_image_at_digest_reference(fake_client) -> None:
    digest = "sha256:" + "a" * 64
    challenge = _make_challenge(digest=digest)
    db = _make_db()
    redis = _FakeRedis()

    await launcher.launch_instance(1, challenge, db, redis)

    assert fake_client.captured_run_kwargs["image"] == f"siege/test@{digest}"
    assert fake_client.captured_run_kwargs["read_only"] is True
    assert fake_client.captured_run_kwargs["cap_drop"] == ["ALL"]
    assert fake_client.captured_run_kwargs["cap_add"] == []


@pytest.mark.asyncio
async def test_launch_emits_profile_and_digest_labels(fake_client) -> None:
    digest = "sha256:" + "b" * 64
    challenge = _make_challenge(digest=digest, profile="malware-sandbox")
    db = _make_db()
    await launcher.launch_instance(1, challenge, db, _FakeRedis())

    labels = fake_client.captured_run_kwargs["labels"]
    assert labels["siege.profile"] == "malware-sandbox"
    assert labels["siege.digest"] == digest
    assert labels["siege.slug"] == "test-challenge"


@pytest.mark.asyncio
async def test_launch_includes_seccomp_in_security_opt(fake_client) -> None:
    digest = "sha256:" + "c" * 64
    challenge = _make_challenge(digest=digest)
    await launcher.launch_instance(1, challenge, _make_db(), _FakeRedis())

    sec_opt = fake_client.captured_run_kwargs["security_opt"]
    assert any(opt.startswith("no-new-privileges") for opt in sec_opt)
    assert any(opt.startswith("seccomp=") for opt in sec_opt)


@pytest.mark.asyncio
async def test_launch_unknown_profile_raises(fake_client) -> None:
    digest = "sha256:" + "d" * 64
    challenge = _make_challenge(digest=digest, profile="not-a-real-profile")
    from app.services.orchestration.profiles import UnknownProfile
    with pytest.raises(UnknownProfile):
        await launcher.launch_instance(1, challenge, _make_db(), _FakeRedis())


@pytest.mark.asyncio
async def test_launch_caps_ttl_at_profile_ceiling(monkeypatch, fake_client) -> None:
    """User-side CONTAINER_TIMEOUT > profile ceiling → clamped."""
    from app.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "CONTAINER_TIMEOUT", 999_999, raising=False)
    digest = "sha256:" + "e" * 64
    challenge = _make_challenge(digest=digest, profile="malware-sandbox")
    out = await launcher.launch_instance(1, challenge, _make_db(), _FakeRedis())

    from datetime import datetime, timezone
    from app.services.orchestration.profiles import get
    profile_max = get("malware-sandbox").ttl_seconds_max
    delta = (out["expires_at"] - datetime.now(timezone.utc)).total_seconds()
    assert delta <= profile_max + 5  # allow scheduler jitter


@pytest.mark.asyncio
async def test_launch_returns_profile_and_digest_in_payload(fake_client) -> None:
    digest = "sha256:" + "f" * 64
    challenge = _make_challenge(digest=digest, profile="default-strict")
    out = await launcher.launch_instance(1, challenge, _make_db(), _FakeRedis())
    assert out["profile"] == "default-strict"
    assert out["digest"] == digest


# ---------------------------------------------------------------------------
# Phase 12 (slice 11) — post-pull digest verification
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_post_pull_digest_match_succeeds(fake_client) -> None:
    digest = "sha256:" + "a" * 64
    challenge = _make_challenge(digest=digest)
    out = await launcher.launch_instance(1, challenge, _make_db(), _FakeRedis())
    assert out["digest"] == digest


@pytest.mark.asyncio
async def test_post_pull_digest_mismatch_kills_container(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The daemon resolved an image whose RepoDigests does NOT include
    the pinned ref → launcher must stop+remove the container, remove
    the network, and raise PostPullDigestMismatch."""

    rogue = ["docker.io/different/image@sha256:" + "0" * 64]
    client = _FakeDockerClient(repo_digests_override=rogue)
    monkeypatch.setattr(
        "app.services.orchestration.docker_client.get", lambda: client
    )
    digest = "sha256:" + "b" * 64
    challenge = _make_challenge(digest=digest)
    db = _make_db()

    with pytest.raises(launcher.PostPullDigestMismatch):
        await launcher.launch_instance(1, challenge, db, _FakeRedis())

    # Cleanup actually fired on the rejected container.
    assert client.containers.last_container is not None
    assert client.containers.last_container.stop_calls == [2]
    assert client.containers.last_container.remove_calls == [True]
    # No ChallengeInstance row added — db.add only got called for the
    # never-flushed instance attempt; we look at the captured side
    # effect: db.add never hit because the verification raised first.
    assert db.add.call_count == 0


@pytest.mark.asyncio
async def test_post_pull_empty_repo_digests_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A daemon returning an image with no RepoDigests at all (cache
    edge case) is treated as a digest mismatch — we refuse to trust
    an unverifiable image."""

    client = _FakeDockerClient(repo_digests_override=[])
    monkeypatch.setattr(
        "app.services.orchestration.docker_client.get", lambda: client
    )
    digest = "sha256:" + "c" * 64
    challenge = _make_challenge(digest=digest)

    with pytest.raises(launcher.PostPullDigestMismatch):
        await launcher.launch_instance(1, challenge, _make_db(), _FakeRedis())


# ---------------------------------------------------------------------------
# Phase 12 follow-up — egress-proxied-sidecar profile
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sidecar_profile_spawns_sidecar_container(
    monkeypatch: pytest.MonkeyPatch, fake_client
) -> None:
    """``egress-proxied-sidecar`` profile launches a per-instance
    tinyproxy alongside the challenge and records its container_id on
    the ``ChallengeInstance``."""

    captured: dict = {}

    def _fake_launch_sidecar(client, *, network_name, allowlist, instance_label, **_):
        captured["network_name"] = network_name
        captured["allowlist"] = list(allowlist)
        captured["instance_label"] = instance_label
        from app.services.orchestration.sidecar import SidecarLaunch

        return SidecarLaunch(
            container_id="sidecar-fake",
            container_name="siege-egress-sidecar-test",
            listen_url="http://siege-egress-sidecar-test:8888",
        )

    import app.services.orchestration.sidecar as sidecar_mod
    monkeypatch.setattr(sidecar_mod, "launch_sidecar", _fake_launch_sidecar)

    digest = "sha256:" + "1" * 64
    config = {
        "profile": "egress-proxied-sidecar",
        "digest": digest,
        "egress_allowlist": ["api.example.com", "*.internal.test"],
    }
    challenge = SimpleNamespace(
        id=42,
        slug="sidecar-target",
        docker_image="siege/test",
        docker_port=8080,
        docker_config=config,
    )
    db = _make_db()

    out = await launcher.launch_instance(1, challenge, db, _FakeRedis())

    assert out["profile"] == "egress-proxied-sidecar"
    assert out["sidecar_container_id"] == "sidecar-fake"
    assert "api.example.com" in captured["allowlist"]
    assert captured["instance_label"] == "1-sidecar-target"
    # The launcher must use the per-instance network it just created.
    assert captured["network_name"].startswith("siege-ch-1-sidecar-target-")


@pytest.mark.asyncio
async def test_sidecar_profile_tears_down_sidecar_on_run_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``containers.run`` raises after the sidecar started, the
    launcher must tear the sidecar down before bubbling the error."""

    teardown_calls: list[str] = []

    def _fake_launch_sidecar(client, *, network_name, allowlist, instance_label, **_):
        from app.services.orchestration.sidecar import SidecarLaunch

        return SidecarLaunch(
            container_id="sidecar-rollback",
            container_name="siege-egress-sidecar-test",
            listen_url="http://siege-egress-sidecar-test:8888",
        )

    def _fake_teardown(client, container_id):
        teardown_calls.append(container_id)
        return True

    import app.services.orchestration.sidecar as sidecar_mod
    monkeypatch.setattr(sidecar_mod, "launch_sidecar", _fake_launch_sidecar)
    monkeypatch.setattr(sidecar_mod, "teardown_sidecar", _fake_teardown)

    class _BoomContainersAPI(_FakeContainersAPI):
        def run(self, **kwargs):  # noqa: D401 — same signature
            raise RuntimeError("containers.run boom")

    client = _FakeDockerClient()
    client.containers = _BoomContainersAPI(client.captured_run_kwargs)
    monkeypatch.setattr(
        "app.services.orchestration.docker_client.get", lambda: client
    )

    digest = "sha256:" + "2" * 64
    challenge = SimpleNamespace(
        id=99,
        slug="sidecar-fail",
        docker_image="siege/test",
        docker_port=8080,
        docker_config={
            "profile": "egress-proxied-sidecar",
            "digest": digest,
            "egress_allowlist": [],
        },
    )

    with pytest.raises(RuntimeError):
        await launcher.launch_instance(1, challenge, _make_db(), _FakeRedis())

    assert teardown_calls == ["sidecar-rollback"]
