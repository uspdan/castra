"""Sprint 9 Phase B — email verification flow."""

from __future__ import annotations

import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


def _extract_token(body_text: str) -> str:
    marker = "?token="
    idx = body_text.find(marker)
    assert idx != -1, f"link missing: {body_text!r}"
    rest = body_text[idx + len(marker):]
    end = next((i for i, c in enumerate(rest) if c in " \n\r\t"), len(rest))
    return rest[:end]


@pytest.fixture(autouse=True)
def _reset_email_capture():
    from app.services.email import reset_captured_emails

    reset_captured_emails()
    yield
    reset_captured_emails()


# ---------------------------------------------------------------------------
# Register flow now triggers a verification email
# ---------------------------------------------------------------------------
class TestRegisterTriggersEmail:
    async def test_register_sends_verification_email(self, client):
        from app.services.email import CAPTURED_EMAILS

        r = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "verifyme@test.local",
                "username": "verifyme",
                "password": "GoodPassword1!",
                "team": "red",
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["user"]["email_verified"] is False

        # Two emails are not expected — just the verify one.
        assert len(CAPTURED_EMAILS) == 1
        email = CAPTURED_EMAILS[0]
        assert email.to == "verifyme@test.local"
        assert "/verify-email?token=" in email.body_text


# ---------------------------------------------------------------------------
# /api/v1/auth/verify-email
# ---------------------------------------------------------------------------
class TestVerifyEmail:
    async def test_redeem_marks_user_verified(
        self, client, db_session
    ):
        from app.models import User
        from app.services.email import CAPTURED_EMAILS

        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "ver@test.local",
                "username": "veru",
                "password": "GoodPassword1!",
                "team": "blue",
            },
        )
        token = _extract_token(CAPTURED_EMAILS[0].body_text)

        r = await client.post(
            "/api/v1/auth/verify-email", json={"token": token}
        )
        assert r.status_code == 200, r.text

        fresh = (
            await db_session.execute(
                select(User).where(User.username == "veru")
            )
        ).scalar_one()
        assert fresh.email_verified is True

    async def test_redeem_is_single_use(
        self, client
    ):
        from app.services.email import CAPTURED_EMAILS

        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "useonce@test.local",
                "username": "useonceu",
                "password": "GoodPassword1!",
                "team": "red",
            },
        )
        token = _extract_token(CAPTURED_EMAILS[0].body_text)

        r1 = await client.post(
            "/api/v1/auth/verify-email", json={"token": token}
        )
        assert r1.status_code == 200
        r2 = await client.post(
            "/api/v1/auth/verify-email", json={"token": token}
        )
        assert r2.status_code == 400

    async def test_unknown_token_400(self, client):
        r = await client.post(
            "/api/v1/auth/verify-email",
            json={"token": "obviously-not-real"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# /api/v1/auth/resend-verification
# ---------------------------------------------------------------------------
class TestResendVerification:
    async def test_resends_for_unverified_user(
        self, client, user_factory, auth_headers
    ):
        from app.services.email import CAPTURED_EMAILS, reset_captured_emails

        user = await user_factory(email="resend@test.local")
        # User is unverified by default.
        reset_captured_emails()

        r = await client.post(
            "/api/v1/auth/resend-verification",
            headers=auth_headers(user),
        )
        assert r.status_code == 202
        assert len(CAPTURED_EMAILS) == 1
        assert CAPTURED_EMAILS[0].to == "resend@test.local"

    async def test_no_email_for_already_verified(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.services.email import CAPTURED_EMAILS, reset_captured_emails
        from app.models import User

        user = await user_factory(email="alreadyver@test.local")
        # Mark verified directly.
        user.email_verified = True
        db_session.add(user)
        await db_session.commit()
        reset_captured_emails()

        r = await client.post(
            "/api/v1/auth/resend-verification",
            headers=auth_headers(user),
        )
        # Same response shape (no enumeration).
        assert r.status_code == 202
        assert CAPTURED_EMAILS == []


# ---------------------------------------------------------------------------
# Sprint 10 Phase C — login gate
# ---------------------------------------------------------------------------
class TestRequireEmailVerifiedGate:
    async def test_default_off_unverified_login_succeeds(
        self, client, user_factory
    ):
        await user_factory(
            email="default@gate.local",
            username="defaultgate",
            password="GoodPass1!",
        )
        # email_verified=False by default; gate is off; login OK.
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "default@gate.local", "password": "GoodPass1!"},
        )
        assert r.status_code == 200
        assert "access_token" in r.json()

    async def test_gate_on_unverified_blocked(
        self, client, user_factory, monkeypatch
    ):
        from app.config import get_settings

        await user_factory(
            email="gated@gate.local",
            username="gateduser",
            password="GoodPass1!",
        )
        monkeypatch.setattr(
            get_settings(), "REQUIRE_EMAIL_VERIFIED", True, raising=False
        )
        try:
            r = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "gated@gate.local",
                    "password": "GoodPass1!",
                },
            )
            assert r.status_code == 403
            assert "verified" in r.json()["detail"].lower()
        finally:
            monkeypatch.setattr(
                get_settings(), "REQUIRE_EMAIL_VERIFIED", False, raising=False
            )

    async def test_gate_on_verified_passes(
        self, client, user_factory, db_session, monkeypatch
    ):
        from app.config import get_settings

        user = await user_factory(
            email="verified@gate.local",
            username="verifieduser",
            password="GoodPass1!",
        )
        user.email_verified = True
        db_session.add(user)
        await db_session.commit()

        monkeypatch.setattr(
            get_settings(), "REQUIRE_EMAIL_VERIFIED", True, raising=False
        )
        try:
            r = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "verified@gate.local",
                    "password": "GoodPass1!",
                },
            )
            assert r.status_code == 200
        finally:
            monkeypatch.setattr(
                get_settings(), "REQUIRE_EMAIL_VERIFIED", False, raising=False
            )
