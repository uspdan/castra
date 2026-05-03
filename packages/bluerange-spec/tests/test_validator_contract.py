"""Contract tests for the public validator surface.

These run inside the spec package's own test suite so the contract
is tested without any platform dependencies — exactly what an
external plugin author has to work against.
"""

from __future__ import annotations

import asyncio
from typing import Any, Mapping

import pytest

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


class _Dummy(Validator):
    name = "dummy"

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        if config.get("bad"):
            raise ValidatorConfigError("bad config")
        return ValidationResult(correct=submission == "ok")


def test_validator_subclass_satisfies_contract():
    v = _Dummy()
    assert v.name == "dummy"
    assert v.requires_subprocess is False
    assert v.default_timeout_s > 0


def test_cannot_instantiate_abstract_validator():
    with pytest.raises(TypeError):
        Validator()  # type: ignore[abstract]


def test_validation_context_is_immutable():
    ctx = ValidationContext(flag_id="f1", challenge_slug="c1")
    with pytest.raises((AttributeError, Exception)):
        ctx.flag_id = "other"  # type: ignore[misc]


def test_validation_result_defaults():
    r = ValidationResult(correct=True)
    assert r.correct is True
    assert r.partial is False
    assert dict(r.details) == {}


def test_validate_returns_result():
    v = _Dummy()
    ctx = ValidationContext(flag_id="f1", challenge_slug="c1")
    result = asyncio.run(v.validate("ok", {}, ctx))
    assert result.correct is True
    result = asyncio.run(v.validate("nope", {}, ctx))
    assert result.correct is False


def test_validator_config_error_subclass():
    v = _Dummy()
    ctx = ValidationContext(flag_id="f1", challenge_slug="c1")
    with pytest.raises(ValidatorConfigError):
        asyncio.run(v.validate("ok", {"bad": True}, ctx))
