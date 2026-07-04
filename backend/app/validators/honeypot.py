"""AI/LLM honeypot validators (BACKLOG: AI honeypot modules).

Extends the ``llm_signal`` family (Sprint 9 Phase C, ADR 0001) with the
three purpose-built validator types the backlog called for:

- ``prompt_injection_detected`` — the player's crafted prompt overrode
  the target's instructions (system-prompt leak, injected directive
  executed). Fails if the model *refused*.
- ``jailbreak_attempt`` — the player elicited harmful / guard-railed
  output. Fails if the model refused.
- ``agent_abuse_trace`` — the player drove an agent through an expected
  ordered chain of tool calls (an attack pattern), with no forbidden
  step.

All three pattern-match against the transcript / tool-call trace the
challenge container captured rather than comparing exact LLM output —
model output drifts across upstream updates even at temp=0, so string
equality is not graded (same rationale as ``llm_signal``).

Bait secrecy is OUT OF SCOPE (manifests may ship plaintext patterns);
the encrypted-bundle path stays queued for private-set distribution.
"""

from __future__ import annotations

from typing import Any, List, Mapping

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)

from app.validators.regex import _compile  # re2/re fallback, prod fail-closed


def _coerce_patterns(
    config: Mapping[str, Any], key: str, *, required: bool, who: str
) -> List[str]:
    """Validate ``config[key]`` is a (non-empty, when required) list of
    non-empty strings and return it."""
    raw = config.get(key)
    if raw is None:
        if required:
            raise ValidatorConfigError(
                f"{who} validator requires '{key}' (non-empty list of strings)"
            )
        return []
    if not isinstance(raw, list) or (required and not raw):
        raise ValidatorConfigError(
            f"{who} validator: '{key}' must be a non-empty list of strings"
        )
    if not all(isinstance(p, str) and p for p in raw):
        raise ValidatorConfigError(
            f"{who} validator: every '{key}' entry must be a non-empty string"
        )
    return raw


def _min_signals(config: Mapping[str, Any], available: int, who: str) -> int:
    raw = config.get("min_signals", 1)
    try:
        value = int(raw) if raw is not None else 1
    except (TypeError, ValueError):
        raise ValidatorConfigError(f"{who} validator: min_signals must be an integer")
    if value < 1:
        raise ValidatorConfigError(f"{who} validator: min_signals must be >= 1")
    if value > available:
        raise ValidatorConfigError(
            f"{who} validator: min_signals > number of signal patterns"
        )
    return value


def _count_hits(patterns: List[str], compiled: List, submission: str) -> List[str]:
    matched: List[str] = []
    for raw, regex in zip(patterns, compiled):
        if regex.search(submission):
            matched.append(raw)
    return matched


class _SignalWithRefusalValidator(Validator):
    """Shared engine: success requires >= min_signals ``signal_key`` hits
    AND no ``refusal_signals`` hit (a refusal means the guardrail held)."""

    requires_subprocess = False
    default_timeout_s = 2.0
    #: config key holding the "success" evidence patterns (set by subclass)
    signal_key = "success_signals"

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        who = self.name
        case_sensitive = bool(config.get("case_sensitive", False))

        signals = _coerce_patterns(config, self.signal_key, required=True, who=who)
        refusals = _coerce_patterns(
            config, "refusal_signals", required=False, who=who
        )
        min_signals = _min_signals(config, len(signals), who)

        signal_re = [_compile(p, case_sensitive=case_sensitive) for p in signals]
        refusal_re = [_compile(p, case_sensitive=case_sensitive) for p in refusals]

        matched = _count_hits(signals, signal_re, submission)
        refused = bool(_count_hits(refusals, refusal_re, submission))

        correct = (len(matched) >= min_signals) and not refused
        return ValidationResult(
            correct=correct,
            details={
                "matched_count": len(matched),
                "min_signals": min_signals,
                "refused": refused,
                "matched_patterns": matched,
            },
        )


class PromptInjectionValidator(_SignalWithRefusalValidator):
    name = "prompt_injection_detected"
    signal_key = "success_signals"


class JailbreakValidator(_SignalWithRefusalValidator):
    name = "jailbreak_attempt"
    signal_key = "harmful_patterns"


class AgentAbuseTraceValidator(Validator):
    """Validate an agent tool-call trace against an expected *ordered*
    attack pattern. Each ``expected_sequence`` pattern must appear after
    the previous one in the submission; any ``forbidden`` hit fails."""

    name = "agent_abuse_trace"
    requires_subprocess = False
    default_timeout_s = 2.0

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        who = self.name
        case_sensitive = bool(config.get("case_sensitive", False))

        expected = _coerce_patterns(
            config, "expected_sequence", required=True, who=who
        )
        forbidden = _coerce_patterns(config, "forbidden", required=False, who=who)

        expected_re = [_compile(p, case_sensitive=case_sensitive) for p in expected]
        forbidden_re = [_compile(p, case_sensitive=case_sensitive) for p in forbidden]

        # Ordered subsequence match: each pattern must be found in the
        # remainder of the transcript after the previous match. Slice
        # rather than pass a pos= arg so the behaviour is identical under
        # the re2 and stdlib-re backends.
        cursor = 0
        matched_steps = 0
        for regex in expected_re:
            hit = regex.search(submission[cursor:])
            if hit is None:
                break
            cursor += hit.end()
            matched_steps += 1

        forbidden_matched = _count_hits(forbidden, forbidden_re, submission)
        ordered_ok = matched_steps == len(expected)
        correct = ordered_ok and not forbidden_matched

        return ValidationResult(
            correct=correct,
            details={
                "matched_steps": matched_steps,
                "expected_steps": len(expected),
                "ordered_complete": ordered_ok,
                "forbidden_hits": len(forbidden_matched),
            },
        )


__all__ = [
    "PromptInjectionValidator",
    "JailbreakValidator",
    "AgentAbuseTraceValidator",
]
