"""Unit tests for the manifest-flag -> dispatch-args conversion.

Regression coverage for the loader/validator hash agreement: the loader
must hash an exact flag's value with the SAME normalisation the
``exact`` validator applies at submission time. Previously the loader
hashed the raw original-case value while telling the validator
``case_sensitive=False``, which made any case-insensitive exact flag
containing an uppercase character impossible to solve.
"""

from __future__ import annotations

import pytest
from bluerange_spec import ExactFlag, ValidationContext

from app.services.challenge_loader.flag_mapping import flag_to_dispatch
from app.validators.exact import ExactValidator, hash_exact_value


def _exact_flag(value: str, *, case_sensitive: bool) -> ExactFlag:
    return ExactFlag(
        id="flag-1", points=100, value=value, case_sensitive=case_sensitive
    )


def test_case_insensitive_exact_flag_hash_matches_canonical_helper() -> None:
    flag = _exact_flag("MixedCaseFlag", case_sensitive=False)

    args = flag_to_dispatch(flag)

    # Loader must store the lower-cased hash so it agrees with what the
    # validator computes for a lower-cased submission.
    assert args.value_hash == hash_exact_value("MixedCaseFlag", case_sensitive=False)
    assert args.config == {"case_sensitive": False}


def test_case_sensitive_exact_flag_preserves_case() -> None:
    flag = _exact_flag("MixedCaseFlag", case_sensitive=True)

    args = flag_to_dispatch(flag)

    assert args.value_hash == hash_exact_value("MixedCaseFlag", case_sensitive=True)
    assert args.config == {"case_sensitive": True}


@pytest.mark.parametrize(
    "submission, should_pass",
    [
        ("MixedCaseFlag", True),   # exact original case
        ("mixedcaseflag", True),   # different case still accepted
        ("MIXEDCASEFLAG", True),
        ("  MixedCaseFlag  ", True),  # surrounding whitespace stripped
        ("wrongflag", False),
    ],
)
async def test_case_insensitive_flag_roundtrips_through_validator(
    submission: str, should_pass: bool
) -> None:
    """End-to-end: a case-insensitive uppercase flag must be solvable.

    This is the exact path that was broken — the loader-produced hash is
    fed straight into the validator the dispatcher would run.
    """
    flag = _exact_flag("MixedCaseFlag", case_sensitive=False)
    args = flag_to_dispatch(flag)

    result = await ExactValidator().validate(
        submission,
        {"value_hash": args.value_hash, **args.config},
        ValidationContext(flag_id="flag-1", challenge_slug="c1"),
    )

    assert result.correct is should_pass
