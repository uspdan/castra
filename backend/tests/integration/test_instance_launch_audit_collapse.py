"""Phase 9 — instance.launch / stop / reset audits commit in same tx."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.models import AuditLedger, ChallengeInstance


class _StubContainer:
    def __init__(self, cid: str = "ctr-collapse", image_ref: str | None = None):
        self.id = cid
        # Phase 12 (slice 11): post-pull digest verification reads
        # ``container.image.attrs["RepoDigests"]`` and refuses to
        # leave a container running unless the pinned ref is
        # present. Default the stub's ``RepoDigests`` to include
        # whatever ``image_ref`` the launcher just passed in so the
        # collapse-test happy path doesn't trip the new gate.
        self.image = SimpleNamespace(
            attrs={"RepoDigests": [image_ref] if image_ref else []}
        )

    def stop(self, timeout=5):
        return None

    def remove(self, force=True):
        return None


class _StubNetwork:
    def __init__(self, name: str):
        self.name = name


class _StubContainersAPI:
    def __init__(self):
        self._by_id: dict[str, _StubContainer] = {}

    def run(self, **kwargs):
        c = _StubContainer(image_ref=kwargs.get("image"))
        self._by_id[c.id] = c
        return c

    def get(self, cid: str):
        if cid not in self._by_id:
            import docker
            raise docker.errors.NotFound(f"no container {cid}")
        return self._by_id[cid]


class _StubNetworksAPI:
    def __init__(self):
        self._by_name: dict[str, _StubNetwork] = {}

    def create(self, name, **kwargs):
        n = _StubNetwork(name)
        self._by_name[name] = n
        return n

    def get(self, name: str):
        if name not in self._by_name:
            import docker
            raise docker.errors.NotFound(f"no network {name}")
        net = self._by_name[name]
        net.remove = MagicMock()
        return net


class _StubDockerClient:
    def __init__(self):
        self.containers = _StubContainersAPI()
        self.networks = _StubNetworksAPI()


@pytest.fixture
def stub_docker(monkeypatch):
    client = _StubDockerClient()
    monkeypatch.setattr(
        "app.services.orchestration.docker_client.get", lambda: client
    )
    return client


async def test_launch_audit_in_same_transaction(
    client, db_session, user_factory, challenge_factory, auth_headers, stub_docker
):
    user = await user_factory()
    challenge = await challenge_factory(slug="audit-collapse-launch")
    challenge.docker_config = {
        "profile": "default-strict",
        "digest": "sha256:" + "1" * 64,
    }
    await db_session.commit()

    pre_seq = (
        await db_session.execute(
            select(AuditLedger.seq).order_by(AuditLedger.seq.desc()).limit(1)
        )
    ).scalar() or 0

    resp = await client.post(
        f"/instances/{challenge.slug}/launch", headers=auth_headers(user)
    )
    assert resp.status_code == 200, resp.text

    rows = (
        await db_session.execute(
            select(AuditLedger).where(
                AuditLedger.event_type == "instance.launch",
                AuditLedger.seq > pre_seq,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["profile"] == "default-strict"
    assert payload["digest"] == "sha256:" + "1" * 64

    inst_rows = (
        await db_session.execute(
            select(ChallengeInstance).where(
                ChallengeInstance.user_id == user.id,
                ChallengeInstance.challenge_id == challenge.id,
            )
        )
    ).scalars().all()
    assert len(inst_rows) == 1
    assert inst_rows[0].applied_profile == "default-strict"
    assert inst_rows[0].applied_digest == "sha256:" + "1" * 64
    assert inst_rows[0].seccomp_profile_sha256 is not None


async def test_launch_failure_rolls_back_instance_and_audit(
    client, db_session, user_factory, challenge_factory, auth_headers, stub_docker
):
    """If the launcher refuses (no digest), no instance row and no audit row."""
    user = await user_factory()
    challenge = await challenge_factory(slug="audit-collapse-fail")
    # Deliberately omit digest — Phase 9 refuses.
    challenge.docker_config = {"profile": "default-strict"}
    await db_session.commit()

    pre_seq = (
        await db_session.execute(
            select(AuditLedger.seq).order_by(AuditLedger.seq.desc()).limit(1)
        )
    ).scalar() or 0

    resp = await client.post(
        f"/instances/{challenge.slug}/launch", headers=auth_headers(user)
    )
    assert resp.status_code == 409

    rows = (
        await db_session.execute(
            select(AuditLedger).where(AuditLedger.seq > pre_seq)
        )
    ).scalars().all()
    assert rows == []

    inst_rows = (
        await db_session.execute(
            select(ChallengeInstance).where(
                ChallengeInstance.user_id == user.id,
                ChallengeInstance.challenge_id == challenge.id,
            )
        )
    ).scalars().all()
    assert inst_rows == []


async def test_stop_audit_in_same_transaction(
    client, db_session, user_factory, challenge_factory, auth_headers, stub_docker
):
    user = await user_factory()
    challenge = await challenge_factory(slug="audit-collapse-stop")
    challenge.docker_config = {
        "profile": "default-strict",
        "digest": "sha256:" + "2" * 64,
    }
    await db_session.commit()

    launch_resp = await client.post(
        f"/instances/{challenge.slug}/launch", headers=auth_headers(user)
    )
    assert launch_resp.status_code == 200
    instance_id = launch_resp.json()["id"]

    pre_seq = (
        await db_session.execute(
            select(AuditLedger.seq).order_by(AuditLedger.seq.desc()).limit(1)
        )
    ).scalar() or 0

    stop_resp = await client.delete(
        f"/instances/{instance_id}", headers=auth_headers(user)
    )
    assert stop_resp.status_code == 200

    rows = (
        await db_session.execute(
            select(AuditLedger).where(
                AuditLedger.event_type == "instance.stop",
                AuditLedger.seq > pre_seq,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
