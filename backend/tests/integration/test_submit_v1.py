"""Integration tests for the v1 (validator-registry) submission path.

The Phase 5 / Phase 6 suite uses the legacy ``flag_hash`` column, which
exercises the dispatcher's legacy branch (``app.services.flag_dispatch
._dispatch_legacy``). These tests build a challenge with v1
``challenge_flags`` rows directly and submit through the public API,
exercising the v1 dispatch branch + validator registry end-to-end.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import (
    AuditLedger,
    Challenge,
    ChallengeFlag,
    Solve,
    TeamType,
)
from app.validators.exact import hash_exact_value


pytestmark = pytest.mark.integration


async def _make_v1_challenge(
    db_session,
    *,
    slug: str,
    flags: list[ChallengeFlag],
    points: int = 100,
) -> Challenge:
    challenge = Challenge(
        slug=slug,
        title=f"V1 {slug}",
        description="V1 challenge",
        category="forensics",
        team=TeamType.blue,
        difficulty=1,
        points=points,
        flag_hash=None,
        hints=[],
        skills=[],
        mitre_techniques=[],
        docker_image="alpine:3.19",
        docker_port=80,
        docker_config={},
        prerequisite_ids=[],
        is_active=True,
        is_released=True,
        released_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        spec_version="1",
    )
    db_session.add(challenge)
    await db_session.commit()
    await db_session.refresh(challenge)
    for f in flags:
        f.challenge_id = challenge.id
        db_session.add(f)
    await db_session.commit()
    await db_session.refresh(challenge)
    return challenge


class TestExactFlagV1:
    async def test_correct_flag_creates_solve(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_challenge(
            db_session,
            slug="v1-exact",
            flags=[
                ChallengeFlag(
                    flag_id="primary",
                    flag_type="exact",
                    points=100,
                    value_hash=hash_exact_value("CTF{REDACTED}"),
                    config={"case_sensitive": True},
                )
            ],
        )

        r = await client.post(
            "/challenges/v1-exact/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["correct"] is True
        assert body["points_awarded"] == 125  # 100 base * 1.25 first-blood

        solve = (
            await db_session.execute(
                select(Solve).where(Solve.user_id == user.id)
            )
        ).scalars().first()
        assert solve is not None

    async def test_wrong_flag_no_solve(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_challenge(
            db_session,
            slug="v1-exact-wrong",
            flags=[
                ChallengeFlag(
                    flag_id="primary",
                    flag_type="exact",
                    points=100,
                    value_hash=hash_exact_value("CTF{REDACTED}"),
                    config={"case_sensitive": True},
                )
            ],
        )

        r = await client.post(
            "/challenges/v1-exact-wrong/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200
        assert r.json()["correct"] is False


class TestRegexFlagV1:
    async def test_pattern_match_wins(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_challenge(
            db_session,
            slug="v1-regex",
            flags=[
                ChallengeFlag(
                    flag_id="r1",
                    flag_type="regex",
                    points=100,
                    config={
                        "pattern": r"CTF\{[a-f0-9]{8}\}",
                        "case_sensitive": True,
                    },
                )
            ],
        )

        r = await client.post(
            "/challenges/v1-regex/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200
        assert r.json()["correct"] is True

    async def test_pattern_miss(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_challenge(
            db_session,
            slug="v1-regex-miss",
            flags=[
                ChallengeFlag(
                    flag_id="r1",
                    flag_type="regex",
                    points=100,
                    config={
                        "pattern": r"CTF\{[a-f0-9]{8}\}",
                        "case_sensitive": True,
                    },
                )
            ],
        )

        r = await client.post(
            "/challenges/v1-regex-miss/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200
        assert r.json()["correct"] is False


class TestMultiPartFlagV1:
    async def test_ordered_match(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_challenge(
            db_session,
            slug="v1-multi",
            flags=[
                ChallengeFlag(
                    flag_id="m1",
                    flag_type="multi_part",
                    points=100,
                    config={"parts": ["alpha", "bravo", "charlie"], "ordered": True},
                )
            ],
        )

        r = await client.post(
            "/challenges/v1-multi/submit",
            headers=auth_headers(user),
            json={"flag": "alpha||bravo||charlie"},
        )
        assert r.status_code == 200
        assert r.json()["correct"] is True


class TestAuditLedgerCarriesFlagId:
    async def test_pass_event_payload_includes_flag_id_and_validator(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_challenge(
            db_session,
            slug="v1-ledger",
            flags=[
                ChallengeFlag(
                    flag_id="primary",
                    flag_type="exact",
                    points=100,
                    value_hash=hash_exact_value("CTF{REDACTED}"),
                    config={"case_sensitive": True},
                )
            ],
        )

        r = await client.post(
            "/challenges/v1-ledger/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200

        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "challenge.flag.submit.pass",
                    AuditLedger.actor_id == str(user.id),
                )
            )
        ).scalars().all()
        assert rows
        payload = rows[-1].payload
        assert payload["flag_id"] == "primary"
        assert payload["validator"] == "exact"
