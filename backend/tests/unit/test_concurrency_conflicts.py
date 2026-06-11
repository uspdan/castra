"""Concurrent-duplicate handling (go-live review fixes).

The read-side "already exists" checks in the submission and MFA
flows race under concurrent requests; the database unique
constraints are the real arbiter. These tests pin the translation
of the resulting ``IntegrityError`` into the same domain outcome
the read-side path produces, instead of an unhandled 500.
"""

from __future__ import annotations

from types import SimpleNamespace

import pyotp
import pytest
from sqlalchemy.exc import IntegrityError

import app.services.flag_submission as flag_submission
from app.services.flag_submission import AlreadySolved, process_submission
from app.services.mfa import (
    MfaEnrolmentFailed,
    confirm_enrolment,
)


pytestmark = pytest.mark.unit


def _integrity_error() -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception("duplicate key"))


# ---------------------------------------------------------------------------
# process_submission — IntegrityError → AlreadySolved
# ---------------------------------------------------------------------------
class TestSubmissionIntegrityConflict:
    @pytest.fixture
    def _single_flag_challenge(self):
        return SimpleNamespace(
            id=1, slug="race-chal", title="Race", flag_definitions=[]
        )

    async def test_single_flag_pass_conflict_maps_to_already_solved(
        self, monkeypatch, _single_flag_challenge
    ):
        async def fake_load(slug, db):
            return _single_flag_challenge

        async def fake_noop(*args, **kwargs):
            return None

        async def fake_dispatch(flag, challenge):
            return SimpleNamespace(
                correct=True, flag_id=None, validator_name=None
            )

        async def fake_record_pass(**kwargs):
            raise _integrity_error()

        monkeypatch.setattr(flag_submission, "_load_challenge", fake_load)
        monkeypatch.setattr(flag_submission, "_ensure_unsolved", fake_noop)
        monkeypatch.setattr(
            flag_submission, "_ensure_prerequisites", fake_noop
        )
        monkeypatch.setattr(
            flag_submission, "dispatch_submission", fake_dispatch
        )
        monkeypatch.setattr(
            flag_submission, "_record_pass", fake_record_pass
        )

        with pytest.raises(AlreadySolved):
            await process_submission(
                user=SimpleNamespace(id=7),
                slug="race-chal",
                submitted_flag="CTF{x}",
                db=object(),
                audit_context={},
            )

    async def test_multi_flag_conflict_maps_to_already_solved(
        self, monkeypatch
    ):
        challenge = SimpleNamespace(
            id=2,
            slug="race-multi",
            title="Race Multi",
            flag_definitions=[
                SimpleNamespace(flag_id="f1"),
                SimpleNamespace(flag_id="f2"),
            ],
        )

        async def fake_load(slug, db):
            return challenge

        async def fake_multi(**kwargs):
            raise _integrity_error()

        monkeypatch.setattr(flag_submission, "_load_challenge", fake_load)
        monkeypatch.setattr(
            flag_submission, "_process_multi_flag_submission", fake_multi
        )

        with pytest.raises(AlreadySolved):
            await process_submission(
                user=SimpleNamespace(id=7),
                slug="race-multi",
                submitted_flag="CTF{x}",
                db=object(),
                audit_context={},
            )


# ---------------------------------------------------------------------------
# confirm_enrolment — recovery-code hash collision retry
# ---------------------------------------------------------------------------
class _FakeNested:
    def __init__(self, should_fail: bool):
        self._should_fail = should_fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._should_fail:
            raise _integrity_error()
        return False


class _FakeSession:
    """Just enough AsyncSession for confirm_enrolment: ``add`` and a
    ``begin_nested`` whose exit raises IntegrityError ``fail_times``
    times before succeeding."""

    def __init__(self, fail_times: int):
        self._fail_times = fail_times
        self.attempts = 0
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    def begin_nested(self) -> _FakeNested:
        self.attempts += 1
        return _FakeNested(self.attempts <= self._fail_times)


def _enrolled_user():
    secret = pyotp.random_base32()
    return (
        SimpleNamespace(id=11, mfa_secret=secret, mfa_enabled=False),
        pyotp.TOTP(secret).now(),
    )


class TestConfirmEnrolmentCollisionRetry:
    async def test_retries_on_collision_then_succeeds(self):
        user, code = _enrolled_user()
        db = _FakeSession(fail_times=1)

        result = await confirm_enrolment(db, user, code)

        assert db.attempts == 2
        assert len(result.recovery_codes) == 10
        assert user.mfa_enabled is True

    async def test_no_collision_single_attempt(self):
        user, code = _enrolled_user()
        db = _FakeSession(fail_times=0)

        result = await confirm_enrolment(db, user, code)

        assert db.attempts == 1
        assert len(result.recovery_codes) == 10

    async def test_gives_up_after_three_collisions(self):
        user, code = _enrolled_user()
        db = _FakeSession(fail_times=3)

        with pytest.raises(MfaEnrolmentFailed):
            await confirm_enrolment(db, user, code)

        assert db.attempts == 3
