"""Exact-match flag validator.

The submission, after stripping leading/trailing whitespace, is hashed
with SHA-256 and compared in constant time against ``value_hash``. The
cleartext flag is never stored — manifest loading derives the hash and
discards the original value. :func:`hash_exact_value` is the canonical
hashing helper for the legacy admin create / update endpoints
(``routers/admin.py``, ``routers/challenges/admin.py``) and the
manifest loader's flag-row builder; Phase 12 (slice 10) consolidated
both onto this single implementation, retiring the redundant
``services/crypto.py`` shim.

``case_sensitive=False`` lower-cases the submission before hashing.
The manifest digest must agree (loader writes
``sha256(value.lower())`` when the manifest declares
``case_sensitive: false``).
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any, Mapping

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


class ExactValidator(Validator):
    name = "exact"
    requires_subprocess = False
    default_timeout_s = 1.0

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        value_hash = config.get("value_hash")
        if not isinstance(value_hash, str) or len(value_hash) != 64:
            raise ValidatorConfigError(
                "exact validator requires 'value_hash' (64-char SHA-256 hex)"
            )
        case_sensitive = bool(config.get("case_sensitive", True))
        normalised = submission.strip()
        if not case_sensitive:
            normalised = normalised.lower()
        digest = hashlib.sha256(normalised.encode("utf-8")).hexdigest()
        # hmac.compare_digest is constant-time over the hex strings —
        # negligible cost here, but keeps timing-side-channel discipline
        # consistent with the rest of the auth surface.
        return ValidationResult(correct=hmac.compare_digest(digest, value_hash))


def hash_exact_value(value: str, *, case_sensitive: bool = True) -> str:
    """Compute the canonical SHA-256 hex digest for an exact-flag value.

    Used by the loader (Phase 7's ``upsert.py``) and the legacy admin
    create/update endpoints so the on-disk hash and the validator's
    expectation always agree.
    """

    normalised = value.strip()
    if not case_sensitive:
        normalised = normalised.lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
