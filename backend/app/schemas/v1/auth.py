"""v1 auth request / response models — locked contract.

The legacy ``/auth/*`` endpoints return ad-hoc dicts (and the user
columns of whatever the SQLAlchemy ``User`` row happens to expose).
The v1 surface freezes the shape: every response is a pydantic model
with ``ConfigDict(extra="forbid")`` so an unintended column cannot
leak. Every request is schema-validated at the boundary
(CLAUDE.md §3.1). Phase 12 (post-slice 21) — front-door
auth migration.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{2,32}$")


class AuthUser(BaseModel):
    """Locked user shape returned alongside auth responses."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    username: str
    display_name: str
    email: str
    role: str
    team: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    # Sprint 7 Phase C — exposed so the frontend Settings page can
    # render the right MFA UI (enrol vs disable). False until the
    # user finishes the confirm step.
    mfa_enabled: bool = False
    # Sprint 9 Phase B — flipped True when the user redeems an
    # email-verification token. Exposed so the frontend can show
    # an "unverified" banner / nudge.
    email_verified: bool = False


class AuthRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=64)
    team: Optional[str] = None

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email format")
        return v

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        v = (v or "").strip()
        if not _USERNAME_RE.match(v):
            raise ValueError(
                "username must be 2-32 chars of letters/digits/_/-/."
            )
        return v

    @field_validator("team")
    @classmethod
    def _team(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ("red", "blue"):
            raise ValueError("team must be 'red' or 'blue'")
        return v


class AuthLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return (v or "").strip().lower()


class AuthRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, max_length=4096)


class AuthLogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: Optional[str] = Field(default=None, max_length=4096)


class AuthTokenPairResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: AuthUser
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthRefreshResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"


class AuthLogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return (v or "").strip().lower()


class ForgotPasswordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)


class ResetPasswordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class ChangePasswordRequest(BaseModel):
    """In-app password change. Requires current password to defend
    against the cookie-theft / unattended-session takeover scenario."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class AccountDeleteRequest(BaseModel):
    """GDPR account deletion. Requires the current password to defend
    against drive-by deletes via stolen access tokens."""

    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128)


class AccountDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class ProfileUpdateRequest(BaseModel):
    """Self-service mutation of the user's own profile fields.

    ``email`` and ``username`` are deliberately not editable here
    (changing them is a separate flow with reverification). ``role``
    is admin-only via /api/v1/admin/users.
    """

    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = Field(default=None, max_length=64)
    team: Optional[str] = None

    @field_validator("display_name")
    @classmethod
    def _display_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("display_name cannot be empty")
        return v

    @field_validator("team")
    @classmethod
    def _team(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if v not in ("red", "blue"):
            raise ValueError("team must be 'red' or 'blue'")
        return v


# ---------------------------------------------------------------------------
# MFA — Sprint 7 Phase C
# ---------------------------------------------------------------------------
class MfaEnrolResponse(BaseModel):
    """Returned by ``POST /api/v1/auth/mfa/enroll``.

    The cleartext secret is shown once so the user can paste it
    into an authenticator if they can't scan the QR. The
    ``provisioning_uri`` is the otpauth:// URL the QR encodes.
    """

    model_config = ConfigDict(extra="forbid")

    secret: str
    provisioning_uri: str


class MfaConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=6, max_length=8)


class MfaConfirmResponse(BaseModel):
    """Returned only on successful confirm-enrol — recovery codes
    are shown once and never persisted in cleartext."""

    model_config = ConfigDict(extra="forbid")

    message: str
    recovery_codes: list[str]


class MfaDisableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=8)


class MfaDisableResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class MfaPendingResponse(BaseModel):
    """Returned from ``POST /api/v1/auth/login`` when the matched
    user has MFA enabled. Replaces the normal token-pair shape;
    client must call ``/auth/mfa/verify`` with the pending token
    + the user's TOTP / recovery code to finish login."""

    model_config = ConfigDict(extra="forbid")

    mfa_required: bool = True
    mfa_pending_token: str


class MfaVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mfa_pending_token: str = Field(min_length=1, max_length=4096)
    code: str = Field(min_length=6, max_length=8)


# ---------------------------------------------------------------------------
# Email verification — Sprint 9 Phase B
# ---------------------------------------------------------------------------
class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=512)


class VerifyEmailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str


class ResendVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
