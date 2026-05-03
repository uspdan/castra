"""Sigma rule validator (blue-team detection-engineering challenges).

The submission is a YAML Sigma rule. The validator parses the rule
with `pysigma`, then evaluates the rule's parsed condition tree
against a fixture event log declared by the challenge. A submission
is correct when its match-set against the fixture exactly equals the
expected match-set the manifest author committed.

Why a custom evaluator (instead of pysigma's built-in backends)
---------------------------------------------------------------

`pysigma` is a rule-to-query converter; it does not ship a generic
in-process evaluator (the closest is the SQL/Elastic/Splunk backends,
which all assume a separate query engine). For a CTF-style validator
we need to score *individual log lines* against the parsed detection
tree. The evaluator below covers the modifier vocabulary the v1
blue-team library uses (``contains``, ``startswith``, ``endswith``,
plain equality, regex). Submissions that rely on unsupported features
(e.g. ``base64offset``) fail fast with a structured config error so
authors know to either avoid them or extend the evaluator.

Why subprocess
--------------

pysigma parses YAML with PyYAML and walks the resulting AST in pure
Python. That is fast in the success case but a maliciously crafted
rule (deeply nested anchor expansion, pathological regex) can burn
arbitrary CPU. The platform's ``run_validator_subprocess`` runs this
validator under :mod:`resource` rlimits, so a hot loop stops at the
``RLIMIT_CPU`` ceiling rather than starving the API event loop.
"""

from __future__ import annotations

import json
import re as _re
from pathlib import Path
from typing import Any, Mapping, Sequence

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


_MAX_RULE_BYTES = 64 * 1024
_MAX_EVENTS = 4096
_DEFAULT_MAX_LOGSOURCE_BYTES = 1024


class SigmaRuleValidator(Validator):
    name = "sigma_rule"
    requires_subprocess = True
    requires_artifacts = True
    default_timeout_s = 5.0

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        if context.artifact_dir is None:
            raise ValidatorConfigError(
                "sigma_rule: validator requires artifact_dir; the platform "
                "did not stage challenge artefacts"
            )
        if len(submission.encode("utf-8")) > _MAX_RULE_BYTES:
            return ValidationResult(correct=False, details={"reason": "oversized_rule"})

        events_path = _events_path(context.artifact_dir, config)
        expected_indices = _expected_indices(config)
        required_logsource = _required_logsource(config)

        try:
            from sigma.rule import SigmaRule
        except ImportError as exc:  # pragma: no cover — dep guaranteed in prod
            raise ValidatorConfigError(
                f"sigma_rule: pysigma not installed: {exc}"
            ) from exc

        try:
            rule = SigmaRule.from_yaml(submission)
        except Exception as exc:  # pysigma raises a few different types
            return ValidationResult(
                correct=False,
                details={"reason": "rule_parse_error", "error": str(exc)[:200]},
            )

        if required_logsource and not _logsource_matches(rule, required_logsource):
            return ValidationResult(
                correct=False, details={"reason": "logsource_mismatch"}
            )

        try:
            condition_root = rule.detection.parsed_condition[0].parsed
        except (AttributeError, IndexError):
            return ValidationResult(
                correct=False, details={"reason": "no_condition"}
            )

        events = _load_events(events_path)
        if events is None:
            raise ValidatorConfigError(
                f"sigma_rule: events fixture missing or malformed at "
                f"{events_path.name}"
            )

        actual_matches = []
        for index, event in enumerate(events):
            if _evaluate(condition_root, event):
                actual_matches.append(index)

        if set(actual_matches) == set(expected_indices):
            return ValidationResult(
                correct=True, details={"matched": actual_matches}
            )
        return ValidationResult(
            correct=False,
            details={
                "reason": "match_set_mismatch",
                "got": actual_matches,
                "expected_count": len(expected_indices),
            },
        )


# ---------------------------------------------------------------------------
# Config / fixture helpers
# ---------------------------------------------------------------------------
def _events_path(artifact_dir: Path, config: Mapping[str, Any]) -> Path:
    name = config.get("events_filename")
    if not isinstance(name, str) or not name:
        raise ValidatorConfigError(
            "sigma_rule: 'events_filename' (string) is required"
        )
    if "/" in name or ".." in name or name.startswith("."):
        raise ValidatorConfigError(
            "sigma_rule: 'events_filename' must be a single filename "
            "(no path separators)"
        )
    return artifact_dir / name


def _expected_indices(config: Mapping[str, Any]) -> Sequence[int]:
    raw = config.get("expected_match_indices")
    if not isinstance(raw, list) or not all(isinstance(i, int) and i >= 0 for i in raw):
        raise ValidatorConfigError(
            "sigma_rule: 'expected_match_indices' must be a list of "
            "non-negative integers"
        )
    return raw


def _required_logsource(config: Mapping[str, Any]) -> dict | None:
    raw = config.get("require_logsource")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValidatorConfigError(
            "sigma_rule: 'require_logsource' must be an object with "
            "category/product/service keys"
        )
    if len(json.dumps(raw)) > _DEFAULT_MAX_LOGSOURCE_BYTES:
        raise ValidatorConfigError("sigma_rule: 'require_logsource' too large")
    allowed = {"category", "product", "service"}
    if not set(raw).issubset(allowed):
        raise ValidatorConfigError(
            f"sigma_rule: 'require_logsource' keys must be subset of {sorted(allowed)}"
        )
    return raw


def _logsource_matches(rule, required: Mapping[str, Any]) -> bool:
    actual = rule.logsource
    for key, expected in required.items():
        if getattr(actual, key, None) != expected:
            return False
    return True


def _load_events(path: Path) -> list[dict] | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list) or len(data) > _MAX_EVENTS:
        return None
    if not all(isinstance(e, dict) for e in data):
        return None
    return data


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def _evaluate(node, event: Mapping[str, Any]) -> bool:
    from sigma.conditions import (
        ConditionAND,
        ConditionFieldEqualsValueExpression,
        ConditionNOT,
        ConditionOR,
        ConditionValueExpression,
    )

    if isinstance(node, ConditionAND):
        return all(_evaluate(child, event) for child in node.args)
    if isinstance(node, ConditionOR):
        return any(_evaluate(child, event) for child in node.args)
    if isinstance(node, ConditionNOT):
        # ConditionNOT has exactly one argument by Sigma grammar.
        if not node.args:
            return False
        return not _evaluate(node.args[0], event)
    if isinstance(node, ConditionFieldEqualsValueExpression):
        return _match_field_value(node.field, node.value, event)
    if isinstance(node, ConditionValueExpression):
        return _match_anywhere(node.value, event)
    raise ValidatorConfigError(
        f"sigma_rule: unsupported condition node {type(node).__name__}"
    )


def _match_field_value(field: str, value, event: Mapping[str, Any]) -> bool:
    if field not in event:
        return False
    return _value_matches(value, event[field])


def _match_anywhere(value, event: Mapping[str, Any]) -> bool:
    return any(_value_matches(value, v) for v in event.values())


def _value_matches(sigma_value, candidate) -> bool:
    from sigma.types import (
        SigmaBool,
        SigmaNull,
        SigmaNumber,
        SigmaRegularExpression,
        SigmaString,
    )

    if isinstance(sigma_value, SigmaNull):
        return candidate is None
    if isinstance(sigma_value, SigmaBool):
        return candidate is sigma_value.boolean
    if isinstance(sigma_value, SigmaNumber):
        try:
            return float(candidate) == float(sigma_value.number)
        except (TypeError, ValueError):
            return False
    if isinstance(sigma_value, SigmaRegularExpression):
        try:
            pattern = _re.compile(_sigma_regexp_to_python(sigma_value))
        except _re.error:
            return False
        return pattern.search(str(candidate)) is not None
    if isinstance(sigma_value, SigmaString):
        regex = _sigma_string_to_regex(sigma_value)
        return regex.fullmatch(str(candidate)) is not None
    # Unknown sigma value type — fail closed rather than silently
    # accepting; this is a programming/manifest authoring error.
    raise ValidatorConfigError(
        f"sigma_rule: unsupported sigma value type "
        f"{type(sigma_value).__name__}"
    )


def _sigma_string_to_regex(value):
    from sigma.types import SigmaString, SpecialChars

    parts: list[str] = []
    for piece in value:
        if piece is SpecialChars.WILDCARD_MULTI:
            parts.append(".*")
        elif piece is SpecialChars.WILDCARD_SINGLE:
            parts.append(".")
        else:
            parts.append(_re.escape(piece))
    pattern = "".join(parts) if parts else ""
    return _re.compile(pattern, _re.DOTALL)


def _sigma_regexp_to_python(value) -> str:
    raw = getattr(value.regexp, "to_plain", lambda: str(value.regexp))()
    if not isinstance(raw, str):
        raw = str(value.regexp)
    return raw
