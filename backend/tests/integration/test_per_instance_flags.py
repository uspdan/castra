"""Per-instance flags (ADR 005 part 2).

The security property under test: for a flag marked ``per_instance``,
only the value minted for *this user's running instance* validates.
The static manifest value must never be accepted — if it were,
per-instance would be theatre and flag sharing would still work.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from castra_spec.builtin.exact import hash_exact_value

from app.models import ChallengeFlag, ChallengeInstance, InstanceStatus

STATIC = "CTF" + "{static-manifest-value}"
MINTED = "CTF" + "{minted-for-this-instance}"


@pytest.fixture
async def per_instance_challenge(db_session, challenge_factory):
    chal = await challenge_factory(slug="pi-flag-chal", points=100)
    # The factory sets a legacy Challenge.flag_hash, which routes
    # dispatch down the v0 path and ignores ChallengeFlag rows. Null it
    # so flag_definitions drives validation, as a v1-loaded challenge.
    chal.flag_hash = None
    db_session.add(
        ChallengeFlag(
            challenge_id=chal.id,
            flag_id="main",
            flag_type="exact",
            points=100,
            value_hash=hash_exact_value(STATIC),
            config={},
            per_instance=True,
        )
    )
    await db_session.commit()
    await db_session.refresh(chal)
    return chal


async def _running_instance(db_session, user, chal, hashes):
    inst = ChallengeInstance(
        user_id=user.id,
        challenge_id=chal.id,
        container_id="c-1",
        container_name="pi-test",
        status=InstanceStatus.running,
        assigned_ip="0.0.0.0",
        assigned_port=10001,
        network_name="n",
        started_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        flag_hashes=hashes,
    )
    db_session.add(inst)
    await db_session.commit()
    return inst


class TestPerInstanceValidation:
    async def test_minted_value_validates(
        self, client, db_session, per_instance_challenge, user_factory, auth_headers
    ):
        user = await user_factory()
        await _running_instance(
            db_session, user, per_instance_challenge,
            {"main": hash_exact_value(MINTED)},
        )
        r = await client.post(
            f"/api/v1/challenges/{per_instance_challenge.slug}/submit",
            json={"flag": MINTED},
            headers=auth_headers(user),
        )
        assert r.status_code == 200
        assert r.json()["correct"] is True

    async def test_static_manifest_value_is_refused(
        self, client, db_session, per_instance_challenge, user_factory, auth_headers
    ):
        # The heart of the feature. The manifest value hashes to the
        # row's value_hash, and it still must not validate.
        user = await user_factory()
        await _running_instance(
            db_session, user, per_instance_challenge,
            {"main": hash_exact_value(MINTED)},
        )
        r = await client.post(
            f"/api/v1/challenges/{per_instance_challenge.slug}/submit",
            json={"flag": STATIC},
            headers=auth_headers(user),
        )
        assert r.status_code == 200
        assert r.json()["correct"] is False

    async def test_no_instance_means_nothing_validates(
        self, client, per_instance_challenge, user_factory, auth_headers
    ):
        user = await user_factory()
        for attempt in (MINTED, STATIC):
            r = await client.post(
                f"/api/v1/challenges/{per_instance_challenge.slug}/submit",
                json={"flag": attempt},
                headers=auth_headers(user),
            )
            assert r.json()["correct"] is False

    async def test_another_users_minted_value_is_refused(
        self, client, db_session, per_instance_challenge, user_factory, auth_headers
    ):
        # Anti-sharing: player B submits player A's flag.
        alice = await user_factory(username="pi-alice")
        bob = await user_factory(username="pi-bob")
        await _running_instance(
            db_session, alice, per_instance_challenge,
            {"main": hash_exact_value(MINTED)},
        )
        await _running_instance(
            db_session, bob, per_instance_challenge,
            {"main": hash_exact_value("CTF" + "{bobs-own-value}")},
        )
        r = await client.post(
            f"/api/v1/challenges/{per_instance_challenge.slug}/submit",
            json={"flag": MINTED},
            headers=auth_headers(bob),
        )
        assert r.json()["correct"] is False

    async def test_ordinary_static_flags_are_unaffected(
        self, client, db_session, challenge_factory, user_factory, auth_headers
    ):
        # Migration-window guarantee: flags without per_instance keep
        # validating exactly as before.
        chal = await challenge_factory(slug="static-flag-chal", points=50)
        chal.flag_hash = None
        db_session.add(
            ChallengeFlag(
                challenge_id=chal.id,
                flag_id="main",
                flag_type="exact",
                points=50,
                value_hash=hash_exact_value(STATIC),
                config={},
                per_instance=False,
            )
        )
        await db_session.commit()
        await db_session.refresh(chal)
        user = await user_factory()
        r = await client.post(
            f"/api/v1/challenges/{chal.slug}/submit",
            json={"flag": STATIC},
            headers=auth_headers(user),
        )
        assert r.json()["correct"] is True
