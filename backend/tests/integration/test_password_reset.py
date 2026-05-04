"""Integration tests for the v1 password-reset flow.

Covers ``POST /api/v1/auth/forgot-password`` and
``POST /api/v1/auth/reset-password`` end-to-end through the FastAPI
test client. The email service is in test mode (``APP_ENV=test``)
so deliveries land in ``CAPTURED_EMAILS`` and tests can extract
the reset link without an SMTP server.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


def _extract_token(body_text: str) -> str:
    """Pull the token query param out of the captured email body."""

    marker = "?token="
    idx = body_text.find(marker)
    assert idx != -1, f"reset link missing in email body: {body_text!r}"
    rest = body_text[idx + len(marker):]
    # Token ends at first whitespace.
    end = next(
        (i for i, c in enumerate(rest) if c in " \n\r\t"), len(rest)
    )
    return rest[:end]


@pytest.fixture(autouse=True)
def _reset_email_capture():
    from app.services.email import reset_captured_emails

    reset_captured_emails()
    yield
    reset_captured_emails()


# ---------------------------------------------------------------------------
# /api/v1/auth/forgot-password
# ---------------------------------------------------------------------------
class TestForgotPassword:
    async def test_real_match_issues_token_and_emails(
        self, client, user_factory, db_session
    ):
        from app.models import PasswordResetToken
        from app.services.email import CAPTURED_EMAILS

        user = await user_factory(
            email="reset-real@test.local", username="resetreal"
        )

        r = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset-real@test.local"},
        )
        assert r.status_code == 202, r.text
        assert "if an account" in r.json()["message"].lower()

        # Token row created + email captured.
        rows = (
            await db_session.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].token_hash
        assert rows[0].used_at is None

        assert len(CAPTURED_EMAILS) == 1
        email = CAPTURED_EMAILS[0]
        assert email.to == "reset-real@test.local"
        assert "/reset-password?token=" in email.body_text

    async def test_unknown_email_still_returns_202(
        self, client, db_session
    ):
        from app.services.email import CAPTURED_EMAILS

        r = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nobody@nowhere.invalid"},
        )
        assert r.status_code == 202
        # No email sent on unknown-account path.
        assert CAPTURED_EMAILS == []

    async def test_inactive_user_returns_202_no_email(
        self, client, user_factory
    ):
        from app.services.email import CAPTURED_EMAILS

        await user_factory(
            email="reset-off@test.local",
            username="resetoff",
            is_active=False,
        )
        r = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "reset-off@test.local"},
        )
        assert r.status_code == 202
        assert CAPTURED_EMAILS == []

    async def test_normalises_email_case(
        self, client, user_factory
    ):
        from app.services.email import CAPTURED_EMAILS

        await user_factory(
            email="case@test.local", username="caseuser"
        )
        r = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "CASE@TEST.REDACTED"},
        )
        assert r.status_code == 202
        assert len(CAPTURED_EMAILS) == 1

    async def test_audit_emit_on_match(
        self, client, user_factory, db_session
    ):
        from app.models import AuditLedger

        await user_factory(
            email="audit-reset@test.local", username="auditreset"
        )
        r = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "audit-reset@test.local"},
        )
        assert r.status_code == 202

        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "auth.password.reset.request"
                )
            )
        ).scalars().all()
        assert rows


# ---------------------------------------------------------------------------
# /api/v1/auth/reset-password
# ---------------------------------------------------------------------------
class TestResetPassword:
    async def test_redeem_sets_new_password(
        self, client, user_factory, db_session
    ):
        from app.models import User
        from app.services.auth import verify_password
        from app.services.email import CAPTURED_EMAILS

        user = await user_factory(
            email="redeem@test.local", username="redeem",
            password="OldPassword1!",
        )
        # Issue.
        await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "redeem@test.local"},
        )
        token = _extract_token(CAPTURED_EMAILS[0].body_text)

        # Redeem.
        r = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "NewPassword2@"},
        )
        assert r.status_code == 200, r.text
        assert "successful" in r.json()["message"].lower()

        # Verify new password works against the row.
        fresh = (
            await db_session.execute(
                select(User).where(User.id == user.id)
            )
        ).scalar_one()
        assert verify_password("NewPassword2@", fresh.hashed_password)
        assert not verify_password(
            "OldPassword1!", fresh.hashed_password
        )

    async def test_redeem_marks_token_used(
        self, client, user_factory, db_session
    ):
        from app.models import PasswordResetToken
        from app.services.email import CAPTURED_EMAILS

        await user_factory(email="useonce@test.local", username="useonce")
        await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "useonce@test.local"},
        )
        token = _extract_token(CAPTURED_EMAILS[0].body_text)
        await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "AnotherPassword3#"},
        )

        # Second use must fail.
        r2 = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "ThirdPassword4$"},
        )
        assert r2.status_code == 400

        # used_at populated on the row.
        rows = (
            await db_session.execute(select(PasswordResetToken))
        ).scalars().all()
        assert rows[-1].used_at is not None

    async def test_unknown_token_returns_400(self, client):
        r = await client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": "obviously-not-a-real-token",
                "new_password": "FreshPassword5%",
            },
        )
        assert r.status_code == 400

    async def test_short_password_rejected(
        self, client, user_factory
    ):
        from app.services.email import CAPTURED_EMAILS

        await user_factory(email="short@test.local", username="shortpw")
        await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "short@test.local"},
        )
        token = _extract_token(CAPTURED_EMAILS[0].body_text)
        r = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "tiny"},
        )
        # Schema validation rejects min_length=8.
        assert r.status_code == 422

    async def test_audit_emit_on_redeem(
        self, client, user_factory, db_session
    ):
        from app.models import AuditLedger
        from app.services.email import CAPTURED_EMAILS

        await user_factory(
            email="redeem-audit@test.local", username="redeemaudit"
        )
        await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "redeem-audit@test.local"},
        )
        token = _extract_token(CAPTURED_EMAILS[0].body_text)
        r = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "GoodPassword6^"},
        )
        assert r.status_code == 200

        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "auth.password.reset.redeem"
                )
            )
        ).scalars().all()
        assert rows
