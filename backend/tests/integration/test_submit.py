"""Integration tests for POST /challenges/{slug}/submit.

Covers the happy path, every documented rejection path, and the audit
ledger emission contract from Phase 2.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
class TestSubmitCorrectFlag:
    async def test_creates_solve_and_first_blood(
        self, client, user_factory, challenge_factory, auth_headers, db_session
    ):
        user = await user_factory()
        challenge = await challenge_factory(
            slug="firstblood", flag="CTF{REDACTED}", points=100
        )

        r = await client.post(
            "/challenges/firstblood/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["correct"] is True
        # First-blood multiplier is 1.25x. 100 * 1.25 = 125.
        # Streak bonus then adds (the user gets streak=1 from this solve,
        # but the streak is computed from the row that was just inserted —
        # calculate_points reads streak BEFORE update_streak, so on a
        # first-ever solve current_streak=0 and contributes nothing).
        assert body["points_awarded"] == 125
        assert body["is_first_blood"] is True

        from app.models import Solve

        solve = (
            await db_session.execute(
                select(Solve).where(
                    Solve.user_id == user.id, Solve.challenge_id == challenge.id
                )
            )
        ).scalar_one()
        assert solve.points_awarded == 125
        assert solve.is_first_blood is True

    async def test_emits_ledger_pass_event(
        self, client, user_factory, challenge_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await challenge_factory(slug="ledger-pass", flag="CTF{REDACTED}")

        from app.models import AuditLedger

        before = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "challenge.flag.submit.pass"
                )
            )
        ).scalars().all()

        r = await client.post(
            "/challenges/ledger-pass/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200

        after = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "challenge.flag.submit.pass"
                )
            )
        ).scalars().all()
        assert len(after) == len(before) + 1
        # Payload must carry the contract Phase 2 declared.
        assert after[-1].payload["challenge_slug"] == "ledger-pass"
        assert "points_awarded" in after[-1].payload
        assert after[-1].payload["is_first_blood"] is True

    async def test_creates_solve_notification(
        self, client, user_factory, challenge_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await challenge_factory(slug="notif", flag="CTF{REDACTED}", title="Notif Chal")

        await client.post(
            "/challenges/notif/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )

        from app.models import Notification

        n = (
            await db_session.execute(
                select(Notification).where(
                    Notification.target_user_id == user.id,
                    Notification.notification_type == "solve",
                )
            )
        ).scalar_one()
        assert "Notif Chal" in n.message


# ---------------------------------------------------------------------------
# Rejections
# ---------------------------------------------------------------------------
class TestSubmitWrongFlag:
    async def test_returns_correct_false(
        self, client, user_factory, challenge_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await challenge_factory(slug="wrong", flag="correct-answer")

        r = await client.post(
            "/challenges/wrong/submit",
            headers=auth_headers(user),
            json={"flag": "definitely-not-the-flag"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["correct"] is False
        assert body["points_awarded"] is None
        assert body["is_first_blood"] is None

        from app.models import Solve

        result = await db_session.execute(
            select(Solve).where(Solve.user_id == user.id)
        )
        assert result.scalar_one_or_none() is None

    async def test_emits_ledger_fail_event(
        self, client, user_factory, challenge_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await challenge_factory(slug="lf", flag="correct-answer")

        from app.models import AuditLedger

        before = len(
            (
                await db_session.execute(
                    select(AuditLedger).where(
                        AuditLedger.event_type == "challenge.flag.submit.fail"
                    )
                )
            ).scalars().all()
        )

        await client.post(
            "/challenges/lf/submit",
            headers=auth_headers(user),
            json={"flag": "wrong-answer"},
        )

        after = len(
            (
                await db_session.execute(
                    select(AuditLedger).where(
                        AuditLedger.event_type == "challenge.flag.submit.fail"
                    )
                )
            ).scalars().all()
        )
        assert after == before + 1


class TestSubmitGuards:
    async def test_404_when_challenge_unknown(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            "/challenges/nope/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 404

    async def test_404_when_challenge_unreleased(
        self, client, user_factory, challenge_factory, auth_headers
    ):
        user = await user_factory()
        await challenge_factory(slug="hidden", is_released=False)
        r = await client.post(
            "/challenges/hidden/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 404

    async def test_400_when_already_solved(
        self, client, user_factory, challenge_factory, auth_headers
    ):
        user = await user_factory()
        await challenge_factory(slug="dup", flag="CTF{REDACTED}")
        first = await client.post(
            "/challenges/dup/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert first.status_code == 200

        again = await client.post(
            "/challenges/dup/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert again.status_code == 400
        assert "already solved" in again.json()["detail"].lower()

    async def test_400_when_prerequisite_unmet(
        self, client, user_factory, challenge_factory, auth_headers
    ):
        user = await user_factory()
        prereq = await challenge_factory(slug="prereq", flag="CTF{REDACTED}")
        await challenge_factory(
            slug="advanced",
            flag="CTF{REDACTED}",
            prerequisite_ids=[prereq.id],
        )

        r = await client.post(
            "/challenges/advanced/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 400
        assert "prerequisite" in r.json()["detail"].lower()

    async def test_succeeds_after_prerequisite_solved(
        self, client, user_factory, challenge_factory, auth_headers
    ):
        user = await user_factory()
        prereq = await challenge_factory(slug="p2-prereq", flag="CTF{REDACTED}")
        await challenge_factory(
            slug="p2-advanced",
            flag="CTF{REDACTED}",
            prerequisite_ids=[prereq.id],
        )

        r1 = await client.post(
            "/challenges/p2-prereq/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r1.status_code == 200

        r2 = await client.post(
            "/challenges/p2-advanced/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r2.status_code == 200
        assert r2.json()["correct"] is True

    async def test_requires_authentication(
        self, client, challenge_factory
    ):
        await challenge_factory(slug="anon", flag="CTF{REDACTED}")
        r = await client.post(
            "/challenges/anon/submit", json={"flag": "CTF{REDACTED}"}
        )
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Hint penalty interaction
# ---------------------------------------------------------------------------
class TestSubmitHintPenalty:
    async def test_hint_used_halves_points(
        self,
        client,
        user_factory,
        challenge_factory,
        auth_headers,
        db_session,
    ):
        user = await user_factory()
        await challenge_factory(
            slug="hinted",
            flag="CTF{REDACTED}",
            points=100,
            hints=["Look at the source."],
        )

        # Unlock a hint so calculate_points sees hint_used=True.
        unlock = await client.post(
            "/challenges/hinted/hint", headers=auth_headers(user)
        )
        assert unlock.status_code == 200

        submit = await client.post(
            "/challenges/hinted/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert submit.status_code == 200
        # Base 100 * first-blood 1.25 * hint 0.5 = 62.5 → rounded to 62 or 63.
        # round() uses banker's rounding in Python; 62.5 rounds to 62.
        assert submit.json()["points_awarded"] == 62
