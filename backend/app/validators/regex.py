"""Regex flag validator.

Prefers ``google-re2`` (linear-time matcher, immune to ReDoS) and
falls back to the standard library ``re`` if the wheel is not
available on the runtime platform. The fallback path is logged once
at module import.

Patterns that compile under ``re`` but not ``re2`` (e.g.
backreferences, lookaround) are rejected at submission time with a
:class:`ValidatorConfigError` — they should already have been
rejected by the manifest loader, but we belt-and-brace here because
the manifest validator only checks ``re``-compileability for IDE
friendliness.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Mapping

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


_logger = logging.getLogger(__name__)

try:  # pragma: no cover — exercised in CI; local fallback varies by platform
    import re2 as _re2  # type: ignore[import-not-found]

    _ENGINE = "re2"
except ImportError:  # pragma: no cover
    # R27 audit finding — until this commit we silently fell back to
    # stdlib ``re`` and warn-logged. That left the regex flag
    # validator exposed to catastrophic-backtracking patterns
    # (ReDoS) on any deploy where google-re2 failed to install.
    # Allow the fallback only when SIEGE_ALLOW_RE_FALLBACK is set
    # (dev escape hatch); production refuses to boot.
    import os as _os

    _re2 = None
    if _os.environ.get("SIEGE_ALLOW_RE_FALLBACK") == "1":
        _ENGINE = "re"
        _logger.warning(
            "google-re2 not importable; falling back to stdlib 're' under "
            "SIEGE_ALLOW_RE_FALLBACK=1. ReDoS patterns will be evaluated "
            "without backtracking protection. Refuse to set this in prod."
        )
    else:
        raise RuntimeError(
            "google-re2 is required for the regex flag validator (ReDoS "
            "defence). Install it via ``pip install google-re2``, or set "
            "SIEGE_ALLOW_RE_FALLBACK=1 for a local dev workaround. The "
            "fallback is refused in production."
        )


def _compile_re2(pattern: str, *, case_sensitive: bool):
    """Compile against re2.

    google-re2 1.1.x uses an Options-only constructor —
    ``re2.compile(pattern, options=Options(case_sensitive=False))``.
    Earlier (0.x) releases of various re2 bindings also exposed flag
    constants, but the maintained ``google-re2`` package no longer
    does, so we pass through Options exclusively.
    """

    assert _re2 is not None
    options = _re2.Options()  # type: ignore[union-attr]
    options.case_sensitive = case_sensitive
    return _re2.compile(pattern, options=options)  # type: ignore[union-attr,call-arg]


def _compile(pattern: str, *, case_sensitive: bool):
    if _re2 is not None:
        try:
            return _compile_re2(pattern, case_sensitive=case_sensitive)
        except Exception as exc:  # re2 raises its own error type
            raise ValidatorConfigError(
                f"regex validator: pattern is not RE2-compatible: {exc}"
            ) from exc
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(pattern, flags)
    except re.error as exc:
        raise ValidatorConfigError(f"regex validator: invalid pattern: {exc}") from exc


class RegexValidator(Validator):
    name = "regex"
    requires_subprocess = False
    default_timeout_s = 1.0

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        pattern = config.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            raise ValidatorConfigError("regex validator requires 'pattern' (string)")
        case_sensitive = bool(config.get("case_sensitive", True))
        compiled = _compile(pattern, case_sensitive=case_sensitive)
        # fullmatch semantics: the manifest spec defines a regex flag
        # as a complete-string match, not a substring search. Authors
        # who want substring semantics anchor with ``.*`` themselves.
        candidate = submission.strip()
        match = compiled.fullmatch(candidate)
        return ValidationResult(correct=match is not None)


def regex_engine() -> str:
    """Return the name of the active regex engine (``"re2"`` or ``"re"``).

    Exposed for diagnostic endpoints / logs only.
    """

    return _ENGINE
