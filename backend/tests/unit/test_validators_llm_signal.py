"""Sprint 9 Phase C — llm_signal validator tests."""

from __future__ import annotations

import pytest

from bluerange_spec import ValidationContext, ValidatorConfigError
from app.validators.llm_signal import LlmSignalValidator


def _ctx() -> ValidationContext:
    return ValidationContext(flag_id="primary", challenge_slug="llm-test")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
class TestLlmSignalValidator:
    @pytest.mark.asyncio
    async def test_single_pattern_match(self):
        v = LlmSignalValidator()
        transcript = "Sure, the customer's SSN is 123-45-6789."
        result = await v.validate(
            transcript,
            {"patterns": [r"\d{3}-\d{2}-\d{4}"]},
            _ctx(),
        )
        assert result.correct is True
        assert result.details["matched_count"] == 1

    @pytest.mark.asyncio
    async def test_no_match_returns_false(self):
        v = LlmSignalValidator()
        result = await v.validate(
            "I'm sorry, I can't share that information.",
            {"patterns": [r"\d{3}-\d{2}-\d{4}"]},
            _ctx(),
        )
        assert result.correct is False
        assert result.details["matched_count"] == 0

    @pytest.mark.asyncio
    async def test_multi_pattern_min_matches(self):
        v = LlmSignalValidator()
        # Need 2 of 3 to match; transcript carries SSN + credit card.
        transcript = (
            "The SSN on file is 123-45-6789 and the card is 4242424242424242."
        )
        result = await v.validate(
            transcript,
            {
                "patterns": [
                    r"\d{3}-\d{2}-\d{4}",   # SSN
                    r"\d{16}",              # credit card-ish
                    r"DOB:\s*\d{4}-\d{2}-\d{2}",  # date of birth (not in transcript)
                ],
                "min_matches": 2,
            },
            _ctx(),
        )
        assert result.correct is True
        assert result.details["matched_count"] >= 2

    @pytest.mark.asyncio
    async def test_min_matches_not_met(self):
        v = LlmSignalValidator()
        result = await v.validate(
            "Only an SSN here: 123-45-6789",
            {
                "patterns": [r"\d{3}-\d{2}-\d{4}", r"\d{16}"],
                "min_matches": 2,
            },
            _ctx(),
        )
        assert result.correct is False
        assert result.details["matched_count"] == 1


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------
class TestLlmSignalConfig:
    @pytest.mark.asyncio
    async def test_missing_patterns(self):
        v = LlmSignalValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("anything", {}, _ctx())

    @pytest.mark.asyncio
    async def test_empty_patterns_list(self):
        v = LlmSignalValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("anything", {"patterns": []}, _ctx())

    @pytest.mark.asyncio
    async def test_non_string_pattern(self):
        v = LlmSignalValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate(
                "anything",
                {"patterns": [r"\d{3}-\d{2}-\d{4}", 12345]},
                _ctx(),
            )

    @pytest.mark.asyncio
    async def test_min_matches_zero_rejected(self):
        v = LlmSignalValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate(
                "anything",
                {"patterns": [r"\d+"], "min_matches": 0},
                _ctx(),
            )

    @pytest.mark.asyncio
    async def test_min_matches_exceeds_pattern_count(self):
        v = LlmSignalValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate(
                "anything",
                {"patterns": [r"\d+"], "min_matches": 5},
                _ctx(),
            )


# ---------------------------------------------------------------------------
# Entry-point registration
# ---------------------------------------------------------------------------
def test_validator_registered_via_entry_point():
    from app.services.validator_registry import build_default_registry

    registry = build_default_registry()
    plugin = registry.get("llm_signal")
    assert plugin is not None
    assert type(plugin).__name__ == "LlmSignalValidator"
