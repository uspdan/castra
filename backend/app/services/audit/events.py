"""Event-type registry for the hash-chained audit ledger.

Adding a new event type:
    1. Add the constant to ``EventType`` and ``_ALLOWED_EVENT_TYPES``.
    2. (Optional) Register a payload validator in ``_PAYLOAD_VALIDATORS``.
    3. Wire the ``append(...)`` call at the emit point.

Event types are intentionally a closed set: callers cannot invent new
strings, so the chain remains queryable by a known vocabulary.
"""

from __future__ import annotations

from typing import Any, Callable, Final


class AuditError(RuntimeError):
    """Raised on any ledger-level invariant violation."""


class ActorType:
    USER: Final = "user"
    SYSTEM: Final = "system"
    ANONYMOUS: Final = "anonymous"


_ALLOWED_ACTOR_TYPES: Final = frozenset(
    {ActorType.USER, ActorType.SYSTEM, ActorType.ANONYMOUS}
)


class EventType:
    AUTH_REGISTER: Final = "auth.register"
    AUTH_LOGIN_SUCCESS: Final = "auth.login.success"
    AUTH_LOGIN_FAILED: Final = "auth.login.failed"
    AUTH_LOGOUT: Final = "auth.logout"
    AUTH_REFRESH: Final = "auth.refresh"
    AUTH_PASSWORD_RESET_REQUEST: Final = "auth.password.reset.request"
    AUTH_PASSWORD_RESET_REDEEM: Final = "auth.password.reset.redeem"
    AUTH_PASSWORD_CHANGE: Final = "auth.password.change"
    AUTH_PROFILE_UPDATE: Final = "auth.profile.update"
    AUTH_ACCOUNT_DELETE: Final = "auth.account.delete"
    AUTH_DATA_EXPORT: Final = "auth.data.export"
    AUTH_MFA_ENROLL: Final = "auth.mfa.enroll"
    AUTH_MFA_CONFIRM: Final = "auth.mfa.confirm"
    AUTH_MFA_DISABLE: Final = "auth.mfa.disable"
    AUTH_MFA_VERIFY_SUCCESS: Final = "auth.mfa.verify.success"
    AUTH_MFA_VERIFY_FAILED: Final = "auth.mfa.verify.failed"
    AUTH_EMAIL_VERIFY_REQUEST: Final = "auth.email.verify.request"
    AUTH_EMAIL_VERIFY_REDEEM: Final = "auth.email.verify.redeem"

    FLAG_SUBMIT_PASS: Final = "challenge.flag.submit.pass"
    FLAG_SUBMIT_FAIL: Final = "challenge.flag.submit.fail"
    CHALLENGE_RELEASED: Final = "challenge.released"

    INSTANCE_LAUNCH: Final = "instance.launch"
    INSTANCE_STOP: Final = "instance.stop"
    INSTANCE_RESET: Final = "instance.reset"
    INSTANCE_EXPIRED: Final = "instance.expired"

    WORKSTATION_LAUNCH: Final = "workstation.launch"
    WORKSTATION_STOP: Final = "workstation.stop"
    WORKSTATION_ATTACHED: Final = "workstation.attached"


_ALLOWED_EVENT_TYPES: Final = frozenset(
    {
        EventType.AUTH_REGISTER,
        EventType.AUTH_LOGIN_SUCCESS,
        EventType.AUTH_LOGIN_FAILED,
        EventType.AUTH_LOGOUT,
        EventType.AUTH_REFRESH,
        EventType.AUTH_PASSWORD_RESET_REQUEST,
        EventType.AUTH_PASSWORD_RESET_REDEEM,
        EventType.AUTH_PASSWORD_CHANGE,
        EventType.AUTH_PROFILE_UPDATE,
        EventType.AUTH_ACCOUNT_DELETE,
        EventType.AUTH_DATA_EXPORT,
        EventType.AUTH_MFA_ENROLL,
        EventType.AUTH_MFA_CONFIRM,
        EventType.AUTH_MFA_DISABLE,
        EventType.AUTH_MFA_VERIFY_SUCCESS,
        EventType.AUTH_MFA_VERIFY_FAILED,
        EventType.AUTH_EMAIL_VERIFY_REQUEST,
        EventType.AUTH_EMAIL_VERIFY_REDEEM,
        EventType.FLAG_SUBMIT_PASS,
        EventType.FLAG_SUBMIT_FAIL,
        EventType.CHALLENGE_RELEASED,
        EventType.INSTANCE_LAUNCH,
        EventType.INSTANCE_STOP,
        EventType.INSTANCE_RESET,
        EventType.INSTANCE_EXPIRED,
        EventType.WORKSTATION_LAUNCH,
        EventType.WORKSTATION_STOP,
        EventType.WORKSTATION_ATTACHED,
    }
)


_PayloadValidator = Callable[[dict[str, Any]], None]


def _require_keys(payload: dict[str, Any], required: tuple[str, ...]) -> None:
    missing = [k for k in required if k not in payload]
    if missing:
        raise AuditError(f"payload missing required keys: {missing}")


def _validate_auth_register(payload: dict[str, Any]) -> None:
    _require_keys(payload, ("username",))


def _validate_auth_login_success(payload: dict[str, Any]) -> None:
    _require_keys(payload, ("username",))


def _validate_auth_login_failed(payload: dict[str, Any]) -> None:
    # R12 audit finding — cleartext ``email`` is no longer carried;
    # callers either drop it (known actor — ``actor_id`` identifies
    # the subject) or replace it with ``email_hash`` (HMAC).
    _require_keys(payload, ("reason",))


def _validate_flag_submit(payload: dict[str, Any]) -> None:
    _require_keys(payload, ("challenge_slug",))


def _validate_flag_submit_pass(payload: dict[str, Any]) -> None:
    _require_keys(payload, ("challenge_slug", "points_awarded", "is_first_blood"))


def _validate_challenge_released(payload: dict[str, Any]) -> None:
    _require_keys(payload, ("challenge_slug", "title", "category", "points"))


def _validate_instance(payload: dict[str, Any]) -> None:
    _require_keys(payload, ("instance_id",))


def _validate_instance_launch(payload: dict[str, Any]) -> None:
    _require_keys(payload, ("instance_id", "challenge_slug"))


def _validate_workstation(payload: dict[str, Any]) -> None:
    _require_keys(payload, ("container",))


def _validate_workstation_attached(payload: dict[str, Any]) -> None:
    _require_keys(payload, ("container", "network", "challenge_slug"))


_PAYLOAD_VALIDATORS: Final[dict[str, _PayloadValidator]] = {
    EventType.AUTH_REGISTER: _validate_auth_register,
    EventType.AUTH_LOGIN_SUCCESS: _validate_auth_login_success,
    EventType.AUTH_LOGIN_FAILED: _validate_auth_login_failed,
    EventType.FLAG_SUBMIT_PASS: _validate_flag_submit_pass,
    EventType.FLAG_SUBMIT_FAIL: _validate_flag_submit,
    EventType.CHALLENGE_RELEASED: _validate_challenge_released,
    EventType.INSTANCE_LAUNCH: _validate_instance_launch,
    EventType.INSTANCE_STOP: _validate_instance,
    EventType.INSTANCE_RESET: _validate_instance,
    EventType.INSTANCE_EXPIRED: _validate_instance,
    EventType.WORKSTATION_LAUNCH: _validate_workstation,
    EventType.WORKSTATION_STOP: _validate_workstation,
    EventType.WORKSTATION_ATTACHED: _validate_workstation_attached,
}


def validate_event(event_type: str, actor_type: str, payload: dict[str, Any]) -> None:
    """Reject unknown event types, unknown actor types, or malformed payloads."""

    if event_type not in _ALLOWED_EVENT_TYPES:
        raise AuditError(f"unknown audit event_type: {event_type!r}")
    if actor_type not in _ALLOWED_ACTOR_TYPES:
        raise AuditError(f"unknown audit actor_type: {actor_type!r}")
    validator = _PAYLOAD_VALIDATORS.get(event_type)
    if validator is not None:
        validator(payload)
