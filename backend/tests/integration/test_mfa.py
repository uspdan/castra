"""Sprint 7 Phase C — MFA / TOTP integration tests.

Covers the four endpoints + the login-flow short-circuit + the
recovery-code redeem path.
"""

from __future__ import annotations

import pyotp
import pytest
from sqlalchemy import select


pytestmark = pytest.mark.integration


async def _enroll_and_confirm(client, user, auth_headers):
    """Helper: walk through enroll → confirm using a real TOTP."""

    er = await client.post(
        "/api/v1/auth/mfa/enroll", headers=auth_headers(user)
    )
    secret = er.json()["secret"]
    totp = pyotp.TOTP(secret)

    cr = await client.post(
        "/api/v1/auth/mfa/confirm",
        headers=auth_headers(user),
        json={"code": totp.now()},
    )
    assert cr.status_code == 200, cr.text
    return secret, cr.json()["recovery_codes"]


# ---------------------------------------------------------------------------
# /api/v1/auth/mfa/enroll
# ---------------------------------------------------------------------------
class TestMfaEnroll:
    async def test_unauthenticated_rejected(self, client):
        r = await client.post("/api/v1/auth/mfa/enroll")
        assert r.status_code in (401, 403)

    async def test_returns_secret_and_uri(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            "/api/v1/auth/mfa/enroll", headers=auth_headers(user)
        )
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"secret", "provisioning_uri"}
        assert body["secret"]
        assert body["provisioning_uri"].startswith("otpauth://totp/")

    async def test_does_not_enable_until_confirmed(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import User

        user = await user_factory()
        await client.post(
            "/api/v1/auth/mfa/enroll", headers=auth_headers(user)
        )
        fresh = (
            await db_session.execute(select(User).where(User.id == user.id))
        ).scalar_one()
        assert fresh.mfa_secret is not None
        assert fresh.mfa_enabled is False


# ---------------------------------------------------------------------------
# /api/v1/auth/mfa/confirm
# ---------------------------------------------------------------------------
class TestMfaConfirm:
    async def test_happy_path(self, client, user_factory, auth_headers, db_session):
        from app.models import User

        user = await user_factory()
        secret, codes = await _enroll_and_confirm(client, user, auth_headers)

        fresh = (
            await db_session.execute(select(User).where(User.id == user.id))
        ).scalar_one()
        assert fresh.mfa_enabled is True
        assert len(codes) == 10
        assert all(len(c) == 8 for c in codes)
        # All codes are unique.
        assert len(set(codes)) == 10

    async def test_wrong_code_rejected(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        await client.post(
            "/api/v1/auth/mfa/enroll", headers=auth_headers(user)
        )
        r = await client.post(
            "/api/v1/auth/mfa/confirm",
            headers=auth_headers(user),
            json={"code": "000000"},
        )
        assert r.status_code == 400

    async def test_confirm_without_enroll_400(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory()
        r = await client.post(
            "/api/v1/auth/mfa/confirm",
            headers=auth_headers(user),
            json={"code": "123456"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# /api/v1/auth/mfa/disable
# ---------------------------------------------------------------------------
class TestMfaDisable:
    async def test_happy_path_with_totp(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import MfaRecoveryCode, User

        user = await user_factory(password="GoodPass1!")
        secret, _ = await _enroll_and_confirm(client, user, auth_headers)
        totp = pyotp.TOTP(secret)

        r = await client.post(
            "/api/v1/auth/mfa/disable",
            headers=auth_headers(user),
            json={"password": "GoodPass1!", "code": totp.now()},
        )
        assert r.status_code == 200, r.text

        fresh = (
            await db_session.execute(select(User).where(User.id == user.id))
        ).scalar_one()
        assert fresh.mfa_enabled is False
        assert fresh.mfa_secret is None

        # Recovery codes wiped.
        rc = (
            await db_session.execute(
                select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id)
            )
        ).scalars().all()
        assert rc == []

    async def test_wrong_password_rejected(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory(password="GoodPass1!")
        secret, _ = await _enroll_and_confirm(client, user, auth_headers)
        totp = pyotp.TOTP(secret)

        r = await client.post(
            "/api/v1/auth/mfa/disable",
            headers=auth_headers(user),
            json={"password": "WrongPass1!", "code": totp.now()},
        )
        assert r.status_code == 401

    async def test_wrong_code_rejected(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory(password="GoodPass1!")
        await _enroll_and_confirm(client, user, auth_headers)
        r = await client.post(
            "/api/v1/auth/mfa/disable",
            headers=auth_headers(user),
            json={"password": "GoodPass1!", "code": "000000"},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Login → /api/v1/auth/mfa/verify
# ---------------------------------------------------------------------------
class TestLoginMfaFlow:
    async def test_login_returns_pending_when_mfa_enabled(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory(
            email="mfaflow@test.local",
            username="mfaflow",
            password="GoodPass1!",
        )
        secret, _ = await _enroll_and_confirm(client, user, auth_headers)

        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "mfaflow@test.local", "password": "GoodPass1!"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body == {
            "mfa_required": True,
            "mfa_pending_token": body.get("mfa_pending_token"),
        }
        assert body["mfa_pending_token"]

    async def test_verify_with_totp_returns_token_pair(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory(
            email="mfaverify@test.local",
            username="mfaverify",
            password="GoodPass1!",
        )
        secret, _ = await _enroll_and_confirm(client, user, auth_headers)

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "mfaverify@test.local", "password": "GoodPass1!"},
        )
        pending = login.json()["mfa_pending_token"]

        totp = pyotp.TOTP(secret)
        r = await client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_pending_token": pending, "code": totp.now()},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["access_token"]
        assert body["refresh_token"]
        assert body["user"]["mfa_enabled"] is True

    async def test_verify_with_recovery_code_consumes_it(
        self, client, user_factory, auth_headers, db_session
    ):
        from app.models import MfaRecoveryCode

        user = await user_factory(
            email="mfarec@test.local",
            username="mfarec",
            password="GoodPass1!",
        )
        secret, recovery_codes = await _enroll_and_confirm(
            client, user, auth_headers
        )

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "mfarec@test.local", "password": "GoodPass1!"},
        )
        pending = login.json()["mfa_pending_token"]

        # Use the first recovery code.
        used = recovery_codes[0]
        r = await client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_pending_token": pending, "code": used},
        )
        assert r.status_code == 200, r.text

        # Recovery code marked used.
        rows = (
            await db_session.execute(
                select(MfaRecoveryCode).where(
                    MfaRecoveryCode.user_id == user.id
                )
            )
        ).scalars().all()
        used_rows = [r for r in rows if r.used_at is not None]
        assert len(used_rows) == 1

        # Re-using the same recovery code fails.
        login2 = await client.post(
            "/api/v1/auth/login",
            json={"email": "mfarec@test.local", "password": "GoodPass1!"},
        )
        pending2 = login2.json()["mfa_pending_token"]
        r2 = await client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_pending_token": pending2, "code": used},
        )
        assert r2.status_code == 401

    async def test_verify_rejects_garbage_pending_token(self, client):
        r = await client.post(
            "/api/v1/auth/mfa/verify",
            json={
                "mfa_pending_token": "not-a-real-token",
                "code": "123456",
            },
        )
        assert r.status_code == 401

    async def test_verify_rejects_wrong_code(
        self, client, user_factory, auth_headers
    ):
        user = await user_factory(
            email="wrongcode@test.local",
            username="wrongcodeuser",
            password="GoodPass1!",
        )
        await _enroll_and_confirm(client, user, auth_headers)

        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "wrongcode@test.local",
                "password": "GoodPass1!",
            },
        )
        pending = login.json()["mfa_pending_token"]
        r = await client.post(
            "/api/v1/auth/mfa/verify",
            json={"mfa_pending_token": pending, "code": "000000"},
        )
        assert r.status_code == 401

    async def test_no_mfa_login_returns_token_pair(
        self, client, user_factory
    ):
        await user_factory(
            email="nomfa@test.local",
            username="nomfa",
            password="GoodPass1!",
        )
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "nomfa@test.local", "password": "GoodPass1!"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert "mfa_required" not in body
