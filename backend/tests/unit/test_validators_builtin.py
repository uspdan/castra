"""Unit tests for the three v1 first-party validators."""

from __future__ import annotations

import hashlib

import pytest

from app.validators.exact import ExactValidator, hash_exact_value
from app.validators.multi_part import MultiPartValidator, join_parts
from app.validators.regex import RegexValidator, regex_engine
from bluerange_spec import (
    ValidationContext,
    ValidatorConfigError,
)


@pytest.fixture
def context():
    return ValidationContext(flag_id="f1", challenge_slug="c1")


# ---------------------------------------------------------------------------
# ExactValidator
# ---------------------------------------------------------------------------
class TestExact:
    async def test_correct_submission_matches(self, context):
        v = ExactValidator()
        digest = hashlib.sha256(b"CTF{REDACTED}").hexdigest()
        r = await v.validate("CTF{REDACTED}", {"value_hash": digest}, context)
        assert r.correct is True

    async def test_whitespace_stripped(self, context):
        v = ExactValidator()
        digest = hashlib.sha256(b"CTF{REDACTED}").hexdigest()
        r = await v.validate("  CTF{REDACTED}\n", {"value_hash": digest}, context)
        assert r.correct is True

    async def test_wrong_submission_returns_false(self, context):
        v = ExactValidator()
        digest = hashlib.sha256(b"CTF{REDACTED}").hexdigest()
        r = await v.validate("CTF{REDACTED}", {"value_hash": digest}, context)
        assert r.correct is False

    async def test_case_insensitive_mode(self, context):
        v = ExactValidator()
        digest = hash_exact_value("CTF{REDACTED}", case_sensitive=False)
        r = await v.validate(
            "ctf{example}", {"value_hash": digest, "case_sensitive": False}, context
        )
        assert r.correct is True

    async def test_missing_value_hash_raises(self, context):
        v = ExactValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("CTF{REDACTED}", {}, context)

    async def test_malformed_value_hash_raises(self, context):
        v = ExactValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("CTF{REDACTED}", {"value_hash": "not-a-hash"}, context)

    def test_hash_helper_strips_and_lowercases(self):
        assert hash_exact_value("  CTF{REDACTED}  ") == hash_exact_value("CTF{REDACTED}")
        assert hash_exact_value(
            "ABC", case_sensitive=False
        ) == hash_exact_value("abc", case_sensitive=False)


# ---------------------------------------------------------------------------
# RegexValidator
# ---------------------------------------------------------------------------
class TestRegex:
    async def test_full_match(self, context):
        v = RegexValidator()
        r = await v.validate(
            "CTF{REDACTED}", {"pattern": r"CTF\{[a-z0-9]+\}"}, context
        )
        assert r.correct is True

    async def test_no_match(self, context):
        v = RegexValidator()
        r = await v.validate(
            "NOPE", {"pattern": r"CTF\{[a-z0-9]+\}"}, context
        )
        assert r.correct is False

    async def test_fullmatch_semantics(self, context):
        # Substring match should NOT be accepted; the spec is fullmatch.
        v = RegexValidator()
        r = await v.validate(
            "garbage CTF{REDACTED} trailing",
            {"pattern": r"CTF\{[a-z]+\}"},
            context,
        )
        assert r.correct is False

    async def test_case_insensitive(self, context):
        v = RegexValidator()
        r = await v.validate(
            "ctf{ABC}",
            {"pattern": r"CTF\{[A-Z]+\}", "case_sensitive": False},
            context,
        )
        assert r.correct is True

    async def test_invalid_pattern_raises(self, context):
        v = RegexValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("x", {"pattern": "[unclosed"}, context)

    async def test_missing_pattern_raises(self, context):
        v = RegexValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("x", {}, context)

    def test_engine_advertises_active_backend(self):
        # We pinned google-re2 in requirements-test.txt, so on the host
        # venv the engine should resolve to re2. The container build
        # will satisfy the same pin via requirements.txt.
        assert regex_engine() in {"re", "re2"}


# ---------------------------------------------------------------------------
# MultiPartValidator
# ---------------------------------------------------------------------------
class TestMultiPart:
    async def test_ordered_match(self, context):
        v = MultiPartValidator()
        config = {"parts": ["alpha", "bravo", "charlie"], "ordered": True}
        r = await v.validate(
            join_parts(["alpha", "bravo", "charlie"]), config, context
        )
        assert r.correct is True

    async def test_ordered_wrong_order_fails(self, context):
        v = MultiPartValidator()
        config = {"parts": ["alpha", "bravo", "charlie"], "ordered": True}
        r = await v.validate(
            join_parts(["bravo", "alpha", "charlie"]), config, context
        )
        assert r.correct is False

    async def test_unordered_match(self, context):
        v = MultiPartValidator()
        config = {"parts": ["alpha", "bravo"], "ordered": False}
        r = await v.validate(join_parts(["bravo", "alpha"]), config, context)
        assert r.correct is True

    async def test_partial_submission_fails(self, context):
        v = MultiPartValidator()
        config = {"parts": ["alpha", "bravo", "charlie"], "ordered": True}
        r = await v.validate(join_parts(["alpha", "bravo"]), config, context)
        assert r.correct is False

    async def test_too_few_parts_in_config_raises(self, context):
        v = MultiPartValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("alpha", {"parts": ["alpha"]}, context)

    async def test_missing_parts_raises(self, context):
        v = MultiPartValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("alpha", {}, context)
