"""Artifact download endpoint (ADR 005).

The security property under test is the allowlist: only paths written
to ``challenge_artifacts`` by the loader are servable. The challenges
tree also contains flag/answer sidecars, so "the file exists" must
never be sufficient — that is the difference between a download
endpoint and an arbitrary-file-read.
"""

from __future__ import annotations


import pytest

from app.models import Challenge, ChallengeArtifact


@pytest.fixture
async def artifact_challenge(db_session, tmp_path, monkeypatch):
    """A released artifact-only challenge whose tree exists on disk."""

    from app.config import get_settings

    slug = "artifact-dl-test"
    chal_dir = tmp_path / slug / "artifacts"
    chal_dir.mkdir(parents=True)
    listed = chal_dir / "incident.log"
    listed.write_text("Apr 20 23:41:14 web01 sshd[4593]: Accepted password\n")
    # Present on disk, absent from the DB — must be unreachable.
    unlisted = chal_dir.parent / ".flag.txt"
    unlisted.write_text("CTF" + "{sidecar-must-never-serve}")

    monkeypatch.setattr(
        get_settings(), "CHALLENGES_DIR", str(tmp_path), raising=False
    )

    challenge = Challenge(
        slug=slug,
        title="Artifact DL",
        description="d",
        category="Threat Hunting",
        team="blue",
        difficulty=1,
        points=100,
        docker_image=None,
        docker_port=None,
        is_active=True,
        is_released=True,
    )
    db_session.add(challenge)
    await db_session.flush()
    db_session.add(
        ChallengeArtifact(
            challenge_id=challenge.id,
            path="artifacts/incident.log",
            sha256="0" * 64,
            size_bytes=listed.stat().st_size,
        )
    )
    await db_session.commit()
    return challenge


class TestArtifactDownload:
    async def test_listed_artifact_downloads(
        self, client, artifact_challenge, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            f"/api/v1/challenges/{artifact_challenge.slug}/artifacts/artifacts/incident.log",
            headers=auth_headers(user),
        )
        assert r.status_code == 200
        assert b"Accepted password" in r.content

    async def test_listing_returns_declared_artifacts(
        self, client, artifact_challenge, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            f"/api/v1/challenges/{artifact_challenge.slug}/artifacts",
            headers=auth_headers(user),
        )
        assert r.status_code == 200
        paths = [a["path"] for a in r.json()["artifacts"]]
        assert paths == ["artifacts/incident.log"]

    async def test_unlisted_file_is_404_even_though_it_exists(
        self, client, artifact_challenge, user_factory, auth_headers
    ):
        # The flag sidecar exists on disk inside the challenge dir. The
        # DB allowlist is the only thing standing between it and the
        # player — this is the test that matters.
        user = await user_factory()
        r = await client.get(
            f"/api/v1/challenges/{artifact_challenge.slug}/artifacts/.flag.txt",
            headers=auth_headers(user),
        )
        assert r.status_code == 404

    async def test_traversal_is_404(
        self, client, artifact_challenge, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            f"/api/v1/challenges/{artifact_challenge.slug}/artifacts/..%2F..%2Fetc%2Fpasswd",
            headers=auth_headers(user),
        )
        assert r.status_code == 404

    async def test_requires_auth(self, client, artifact_challenge):
        r = await client.get(
            f"/api/v1/challenges/{artifact_challenge.slug}/artifacts/artifacts/incident.log"
        )
        assert r.status_code == 401

    async def test_unreleased_challenge_is_404(
        self, client, artifact_challenge, db_session, user_factory, auth_headers
    ):
        artifact_challenge.is_released = False
        await db_session.commit()
        user = await user_factory()
        r = await client.get(
            f"/api/v1/challenges/{artifact_challenge.slug}/artifacts",
            headers=auth_headers(user),
        )
        assert r.status_code == 404

    async def test_listed_but_missing_on_disk_is_503(
        self, client, artifact_challenge, db_session, user_factory, auth_headers
    ):
        db_session.add(
            ChallengeArtifact(
                challenge_id=artifact_challenge.id,
                path="artifacts/ghost.bin",
                sha256="1" * 64,
            )
        )
        await db_session.commit()
        user = await user_factory()
        r = await client.get(
            f"/api/v1/challenges/{artifact_challenge.slug}/artifacts/artifacts/ghost.bin",
            headers=auth_headers(user),
        )
        assert r.status_code == 503


class TestArtifactOnlyLaunch:
    async def test_launch_of_artifact_only_challenge_is_409(
        self, client, artifact_challenge, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            f"/instances/{artifact_challenge.slug}/launch",
            headers=auth_headers(user),
        )
        assert r.status_code == 409
        assert "artifact" in r.json()["detail"].lower()

    async def test_detail_reports_has_container_false(
        self, client, artifact_challenge, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.get(
            f"/challenges/{artifact_challenge.slug}",
            headers=auth_headers(user),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["has_container"] is False
        assert [a["path"] for a in body["artifacts"]] == ["artifacts/incident.log"]
