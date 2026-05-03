"""Multi-part flag validator.

A multi-part flag declares an ordered (or unordered) list of
sub-strings the user must submit together to capture the flag. v1's
submission API accepts a single string per call, so the protocol is:
the user concatenates the parts using the canonical separator
``"||"`` (chosen because flag values cannot contain it — see manifest
schema validation).

Constant-time comparison guards against timing oracles on individual
parts. Returning ``correct=True`` when the submission matches the
expected multi-set respects the ``ordered`` flag.
"""

from __future__ import annotations

import hmac
from typing import Any, List, Mapping

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


_SEPARATOR = "||"


class MultiPartValidator(Validator):
    name = "multi_part"
    requires_subprocess = False
    default_timeout_s = 1.0

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        parts_cfg = config.get("parts")
        if not isinstance(parts_cfg, list) or len(parts_cfg) < 2:
            raise ValidatorConfigError(
                "multi_part validator requires 'parts' (list of >=2 strings)"
            )
        ordered = bool(config.get("ordered", True))
        expected: List[str] = [str(p) for p in parts_cfg]
        submitted = [s.strip() for s in submission.split(_SEPARATOR) if s.strip() != ""]
        if len(submitted) != len(expected):
            return ValidationResult(correct=False)
        if ordered:
            ok = all(hmac.compare_digest(a, b) for a, b in zip(submitted, expected))
        else:
            # Set comparison with multiplicity preserved. We don't use
            # constant-time compare for set membership — leaking the
            # presence/absence of a part is intrinsic to the operation.
            ok = sorted(submitted) == sorted(expected)
        return ValidationResult(correct=ok)


def join_parts(parts: List[str]) -> str:
    """Helper for tests / docs: joins parts with the canonical separator."""

    return _SEPARATOR.join(parts)
