"""Chain-of-custody validator.

Blue-team challenges in the forensics track ask players to assemble an
evidence-handling timeline: who touched the artefact, what they did,
when, and a SHA-256 of the artefact at that moment. The validator
verifies the submitted chain is internally consistent (each step's
``prev_hash`` matches the previous step's ``this_hash``), monotonic in
time, and built from an approved actor / action vocabulary declared
by the challenge.

Submission format (JSON string)::

    [
      {"actor": "ir-analyst-1", "action": "acquire",
       "timestamp": "2026-04-01T08:00:00Z",
       "this_hash": "<64-hex>", "prev_hash": null},
      {"actor": "ir-analyst-2", "action": "transport",
       "timestamp": "2026-04-01T08:30:00Z",
       "this_hash": "<64-hex>", "prev_hash": "<previous this_hash>"},
      ...
    ]

Config::

    {
      "expected_steps": ["acquire", "transport", "image", "analyse"],
      "allowed_actors": ["ir-analyst-1", "ir-analyst-2", ...],
      "expected_final_hash": "<optional 64-hex>"
    }

The validator is deliberately strict — a successful submission must
contain *exactly* the steps in ``expected_steps`` (order-sensitive),
every actor must appear in ``allowed_actors``, every hash must be a
canonical 64-hex SHA-256, every ``prev_hash`` must match the prior
``this_hash`` (first step has ``prev_hash: null``), and timestamps
must be ISO-8601 strictly increasing.
"""

from __future__ import annotations

import hmac
import json
import re
from datetime import datetime, timezone
from typing import Any, List, Mapping

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_STEPS = 64
_MAX_SUBMISSION_BYTES = 256 * 1024  # 256 KiB envelope cap


class ChainOfCustodyValidator(Validator):
    name = "chain_of_custody"
    requires_subprocess = False
    default_timeout_s = 1.0

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        expected_steps = _expected_steps(config)
        allowed_actors = _allowed_actors(config)
        expected_final = _expected_final_hash(config)

        if len(submission.encode("utf-8")) > _MAX_SUBMISSION_BYTES:
            return ValidationResult(correct=False, details={"reason": "oversized"})

        try:
            parsed = json.loads(submission)
        except json.JSONDecodeError:
            return ValidationResult(correct=False, details={"reason": "not_json"})

        if not isinstance(parsed, list) or not (1 <= len(parsed) <= _MAX_STEPS):
            return ValidationResult(correct=False, details={"reason": "shape"})

        if len(parsed) != len(expected_steps):
            return ValidationResult(
                correct=False,
                details={"reason": "step_count", "expected": len(expected_steps)},
            )

        prev_hash = None
        prev_ts: datetime | None = None
        for index, step in enumerate(parsed):
            ok, reason = _check_step(
                step,
                index=index,
                expected_action=expected_steps[index],
                allowed_actors=allowed_actors,
                expected_prev=prev_hash,
                prev_ts=prev_ts,
            )
            if not ok:
                return ValidationResult(
                    correct=False, details={"reason": reason, "step_index": index}
                )
            prev_hash = step["this_hash"]
            prev_ts = _parse_timestamp(step["timestamp"])

        if expected_final is not None and not hmac.compare_digest(
            str(prev_hash or ""), expected_final
        ):
            return ValidationResult(correct=False, details={"reason": "final_hash"})

        return ValidationResult(correct=True)


def _expected_steps(config: Mapping[str, Any]) -> List[str]:
    steps = config.get("expected_steps")
    if not isinstance(steps, list) or not steps or not all(
        isinstance(s, str) and s for s in steps
    ):
        raise ValidatorConfigError(
            "chain_of_custody: 'expected_steps' must be a non-empty list of strings"
        )
    if len(steps) > _MAX_STEPS:
        raise ValidatorConfigError(
            f"chain_of_custody: 'expected_steps' exceeds {_MAX_STEPS} entries"
        )
    return [str(s) for s in steps]


def _allowed_actors(config: Mapping[str, Any]) -> set[str]:
    actors = config.get("allowed_actors")
    if not isinstance(actors, list) or not actors or not all(
        isinstance(a, str) and a for a in actors
    ):
        raise ValidatorConfigError(
            "chain_of_custody: 'allowed_actors' must be a non-empty list of strings"
        )
    return {str(a) for a in actors}


def _expected_final_hash(config: Mapping[str, Any]) -> str | None:
    final = config.get("expected_final_hash")
    if final is None:
        return None
    if not isinstance(final, str) or not _SHA256_RE.match(final):
        raise ValidatorConfigError(
            "chain_of_custody: 'expected_final_hash' must be a 64-char hex SHA-256"
        )
    return final


def _check_step(
    step: Any,
    *,
    index: int,
    expected_action: str,
    allowed_actors: set[str],
    expected_prev: str | None,
    prev_ts: datetime | None,
) -> tuple[bool, str]:
    if not isinstance(step, dict):
        return False, "step_shape"
    actor = step.get("actor")
    action = step.get("action")
    timestamp = step.get("timestamp")
    this_hash = step.get("this_hash")
    prev_hash = step.get("prev_hash")

    if not isinstance(actor, str) or actor not in allowed_actors:
        return False, "actor"
    if not isinstance(action, str) or action != expected_action:
        return False, "action"
    if not isinstance(this_hash, str) or not _SHA256_RE.match(this_hash):
        return False, "this_hash"
    if index == 0:
        if prev_hash is not None:
            return False, "first_prev_hash_must_be_null"
    else:
        if not isinstance(prev_hash, str) or not _SHA256_RE.match(prev_hash):
            return False, "prev_hash"
        if not hmac.compare_digest(prev_hash, expected_prev or ""):
            return False, "chain_break"

    parsed_ts = _parse_timestamp(timestamp)
    if parsed_ts is None:
        return False, "timestamp"
    if prev_ts is not None and parsed_ts <= prev_ts:
        return False, "non_monotonic"

    return True, ""


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    candidate = value
    # ``fromisoformat`` doesn't accept the trailing 'Z' on stdlib 3.10.
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # Reject naive timestamps so chains submitted from clients in
        # different zones can't accidentally match. The challenge
        # author encodes the source-of-truth zone in their fixture.
        return None
    return parsed.astimezone(timezone.utc)
