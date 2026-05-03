"""Integration tests for the v1 write endpoints.

Covers ``POST /api/v1/challenges/{slug}/submit`` and
``POST /api/v1/challenges/{slug}/hint`` end-to-end through the FastAPI
test client. Re-uses the platform's testcontainer Postgres + Redis so
the rate-limit dependency, audit ledger, and Solve / HintUnlock rows
all run against real backends.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import AuditLedger, HintUnlock, Solve


pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# POST /api/v1/challenges/{slug}/submit
# ---------------------------------------------------------------------------
class TestSubmitFlag:
    async def test_unauthenticated_rejected(self, client):
        r = await client.post(
            "/api/v1/challenges/anything/submit", json={"flag": "x"}
        )
        assert r.status_code in (401, 403)

    async def test_missing_challenge_returns_404(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            "/api/v1/challenges/does-not-exist/submit",
            headers=auth_headers(user),
            json={"flag": "x"},
        )
        assert r.status_code == 404

    async def test_correct_flag_creates_solve(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-submit-ok", flag="CTF{REDACTED}")
        r = await client.post(
            "/api/v1/challenges/v1-submit-ok/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {
            "correct", "points_awarded", "is_first_blood",
            "flag_id", "validator",
        }
        assert body["correct"] is True
        assert body["points_awarded"] is not None
        assert body["points_awarded"] > 0

        solve = (
            await db_session.execute(
                select(Solve).where(Solve.user_id == user.id)
            )
        ).scalars().first()
        assert solve is not None

    async def test_wrong_flag_no_solve(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-submit-wrong", flag="CTF{REDACTED}")
        r = await client.post(
            "/api/v1/challenges/v1-submit-wrong/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["correct"] is False
        assert body["points_awarded"] is None
        assert body["flag_id"] is None

        solve = (
            await db_session.execute(
                select(Solve).where(Solve.user_id == user.id)
            )
        ).scalars().first()
        assert solve is None

    async def test_already_solved_returns_409(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-submit-twice", flag="CTF{REDACTED}")
        first = await client.post(
            "/api/v1/challenges/v1-submit-twice/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert first.status_code == 200
        second = await client.post(
            "/api/v1/challenges/v1-submit-twice/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert second.status_code == 409
        assert "already solved" in second.json()["detail"].lower()

    async def test_prerequisite_not_met_returns_412(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        user = await user_factory()
        prereq = await challenge_factory(
            slug="v1-prereq-1", flag="CTF{REDACTED}"
        )
        gated = await challenge_factory(
            slug="v1-prereq-gated",
            flag="CTF{REDACTED}",
            prerequisite_ids=[prereq.id],
        )
        r = await client.post(
            f"/api/v1/challenges/{gated.slug}/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 412
        # 412 detail is structured so the UI can list missing slugs.
        detail = r.json()["detail"]
        assert isinstance(detail, dict)
        assert detail["message"]
        assert detail["missing_slugs"] == ["v1-prereq-1"]

    async def test_prerequisite_not_met_lists_multiple_slugs(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        a = await challenge_factory(slug="v1-prereq-a", flag="CTF{REDACTED}")
        b = await challenge_factory(slug="v1-prereq-b", flag="CTF{REDACTED}")
        gated = await challenge_factory(
            slug="v1-prereq-multi",
            flag="CTF{REDACTED}",
            prerequisite_ids=[a.id, b.id],
        )
        r = await client.post(
            f"/api/v1/challenges/{gated.slug}/submit",
            headers=auth_headers(user),
            json={"flag": "CTF{REDACTED}"},
        )
        assert r.status_code == 412
        detail = r.json()["detail"]
        assert set(detail["missing_slugs"]) == {"v1-prereq-a", "v1-prereq-b"}

    async def test_correct_submission_emits_audit_ledger(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-submit-audit", flag="CTF{REDACTED}")
        r = await client.post(
            "/api/v1/challenges/v1-submit-audit/submit",
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


# ---------------------------------------------------------------------------
# POST /api/v1/challenges/{slug}/hint
# ---------------------------------------------------------------------------
class TestUnlockHint:
    async def test_unauthenticated_rejected(self, client):
        r = await client.post("/api/v1/challenges/anything/hint")
        assert r.status_code in (401, 403)

    async def test_missing_challenge_returns_404(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            "/api/v1/challenges/does-not-exist/hint",
            headers=auth_headers(user),
        )
        assert r.status_code == 404

    async def test_no_hints_returns_409(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-hint-empty", hints=[])
        r = await client.post(
            "/api/v1/challenges/v1-hint-empty/hint",
            headers=auth_headers(user),
        )
        assert r.status_code == 409

    async def test_unlock_legacy_string_hint(
        self, client, user_factory, auth_headers, challenge_factory, db_session
    ):
        user = await user_factory()
        await challenge_factory(
            slug="v1-hint-string",
            hints=["look under the bed"],
        )
        r = await client.post(
            "/api/v1/challenges/v1-hint-string/hint",
            headers=auth_headers(user),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) == {"index", "text", "cost"}
        assert body["index"] == 0
        assert body["text"] == "look under the bed"
        assert body["cost"] == 0

        unlocks = (
            await db_session.execute(
                select(HintUnlock).where(HintUnlock.user_id == user.id)
            )
        ).scalars().all()
        assert len(unlocks) == 1

    async def test_unlock_v1_dict_hint_returns_cost(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(
            slug="v1-hint-dict",
            hints=[{"text": "use strings(1)", "cost": 25}],
        )
        r = await client.post(
            "/api/v1/challenges/v1-hint-dict/hint",
            headers=auth_headers(user),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["text"] == "use strings(1)"
        assert body["cost"] == 25

    async def test_all_hints_unlocked_returns_409(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(slug="v1-hint-exhaust", hints=["only one"])
        first = await client.post(
            "/api/v1/challenges/v1-hint-exhaust/hint",
            headers=auth_headers(user),
        )
        assert first.status_code == 200
        second = await client.post(
            "/api/v1/challenges/v1-hint-exhaust/hint",
            headers=auth_headers(user),
        )
        assert second.status_code == 409
        assert "all hints" in second.json()["detail"].lower()

    async def test_two_hints_unlock_in_order(
        self, client, user_factory, auth_headers, challenge_factory
    ):
        user = await user_factory()
        await challenge_factory(
            slug="v1-hint-two",
            hints=["first", "second"],
        )
        first = await client.post(
            "/api/v1/challenges/v1-hint-two/hint",
            headers=auth_headers(user),
        )
        second = await client.post(
            "/api/v1/challenges/v1-hint-two/hint",
            headers=auth_headers(user),
        )
        assert first.json()["index"] == 0
        assert first.json()["text"] == "first"
        assert second.json()["index"] == 1
        assert second.json()["text"] == "second"
