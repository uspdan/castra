"""Attack-chain validator (MITRE ATT&CK technique sequences).

Blue-team attribution challenges ask players to reconstruct an
adversary's path through ATT&CK techniques. The submission is an
ordered list of technique IDs (e.g.
``T1566.001 -> T1059.001 -> T1486``). The validator verifies the
submitted chain covers a *required* sub-sequence in order, with optional
distractor steps allowed only when the manifest enables them.

Submission format
-----------------

A whitespace- or arrow-separated list of ATT&CK technique IDs::

    T1566.001 -> T1059.001 -> T1486

Acceptable separators are: whitespace, ``,``, ``;``, ``->``, ``→``.
The validator normalises to upper-case and de-duplicates consecutive
duplicates.

Config
------

::

    {
      "required_chain": ["T1566.001", "T1059.001", "T1486"],
      "allow_distractors": false,    # default false
      "min_steps": 3,                # optional; defaults to len(required_chain)
      "max_steps": 12                # optional cap on submission length
    }

Decision rules
--------------

* When ``allow_distractors`` is False the submission must equal
  ``required_chain`` exactly (after normalisation).
* When ``allow_distractors`` is True the submission must be a
  *subsequence* of itself that contains every entry in
  ``required_chain`` in the same order; entries not in
  ``required_chain`` are tolerated.
* Submissions longer than ``max_steps`` are rejected outright.
"""

from __future__ import annotations

import re
from typing import Any, List, Mapping

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


_TECHNIQUE_RE = re.compile(r"^T\d{4}(?:\.\d{3})?$")
_SEPARATORS_RE = re.compile(r"\s*(?:->|→|,|;|\s)\s*")
_DEFAULT_MAX_STEPS = 32
_HARD_MAX_SUBMISSION_BYTES = 8 * 1024


class AttackChainValidator(Validator):
    name = "attack_chain"
    requires_subprocess = False
    default_timeout_s = 1.0

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        required = _required_chain(config)
        allow_distractors = bool(config.get("allow_distractors", False))
        min_steps = int(config.get("min_steps", len(required)))
        max_steps = int(config.get("max_steps", _DEFAULT_MAX_STEPS))
        if min_steps < 1 or max_steps < min_steps or max_steps > _DEFAULT_MAX_STEPS:
            raise ValidatorConfigError(
                "attack_chain: invalid min_steps/max_steps bounds"
            )

        if len(submission.encode("utf-8")) > _HARD_MAX_SUBMISSION_BYTES:
            return ValidationResult(correct=False, details={"reason": "oversized"})

        try:
            tokens = _tokenise(submission)
        except _BadToken as exc:
            return ValidationResult(
                correct=False, details={"reason": "bad_token", "token": exc.token}
            )

        if not (min_steps <= len(tokens) <= max_steps):
            return ValidationResult(
                correct=False,
                details={"reason": "step_count", "got": len(tokens)},
            )

        if not allow_distractors:
            ok = tokens == required
            return ValidationResult(
                correct=ok,
                details={"reason": "exact_match"} if not ok else {},
            )

        # Subsequence check: walk required while consuming tokens; the
        # full required list must be matched in order.
        idx = 0
        for token in tokens:
            if idx < len(required) and token == required[idx]:
                idx += 1
        if idx != len(required):
            return ValidationResult(
                correct=False,
                details={"reason": "missing_required", "matched_up_to": idx},
            )
        return ValidationResult(correct=True)


def _required_chain(config: Mapping[str, Any]) -> List[str]:
    chain = config.get("required_chain")
    if not isinstance(chain, list) or not chain:
        raise ValidatorConfigError(
            "attack_chain: 'required_chain' must be a non-empty list"
        )
    if len(chain) > _DEFAULT_MAX_STEPS:
        raise ValidatorConfigError(
            f"attack_chain: 'required_chain' exceeds {_DEFAULT_MAX_STEPS} entries"
        )
    out: List[str] = []
    for item in chain:
        if not isinstance(item, str):
            raise ValidatorConfigError(
                "attack_chain: 'required_chain' entries must be strings"
            )
        normalised = item.strip().upper()
        if not _TECHNIQUE_RE.match(normalised):
            raise ValidatorConfigError(
                f"attack_chain: invalid technique id in required_chain: {item!r}"
            )
        out.append(normalised)
    return out


class _BadToken(Exception):
    def __init__(self, token: str) -> None:
        self.token = token
        super().__init__(token)


def _tokenise(submission: str) -> List[str]:
    if not submission.strip():
        return []
    raw_parts = [p for p in _SEPARATORS_RE.split(submission.strip()) if p]
    out: List[str] = []
    for part in raw_parts:
        token = part.upper()
        if not _TECHNIQUE_RE.match(token):
            raise _BadToken(token)
        # Collapse consecutive duplicates — the chain's ordering is
        # what matters; an analyst writing "T1566.001, T1566.001" is
        # not adding a step.
        if not out or out[-1] != token:
            out.append(token)
    return out
