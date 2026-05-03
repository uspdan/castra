"""Cloud misconfiguration validator.

Cloud-security challenges expose a synthetic IaC bundle (Terraform
plan, CloudFormation template, raw resource JSON) and ask the player
to enumerate the misconfigurations they find. The submission is a
JSON list of ``{resource, finding}`` pairs the player identifies.

Submission format (JSON string)::

    [
      {"resource": "aws_s3_bucket.public_bucket", "finding": "PUBLIC_READ_ACL"},
      {"resource": "aws_security_group.wide_open", "finding": "INGRESS_0_0_0_0_22"},
      ...
    ]

Config::

    {
      "expected_findings": [
        {"resource": "aws_s3_bucket.public_bucket",
         "finding": "PUBLIC_READ_ACL", "severity": "critical"},
        {"resource": "aws_security_group.wide_open",
         "finding": "INGRESS_0_0_0_0_22", "severity": "high"},
        ...
      ],
      "must_include_severities": ["critical"],   # optional
      "min_findings": 1,                         # optional, default len(expected)
      "allow_extra": false                       # default false
    }

Decision rules
--------------

* Submission must be a list of objects each carrying ``resource`` +
  ``finding`` strings.
* Every submitted ``(resource, finding)`` pair must match one in
  ``expected_findings`` (set membership, unordered) — unknown
  fabrications are rejected unless ``allow_extra`` is true.
* The match set must cover every ``expected_findings`` entry whose
  severity is in ``must_include_severities`` (defence in depth: the
  critical findings are mandatory).
* The match count must be ``>= min_findings``.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, List, Mapping, Set, Tuple

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


_MAX_SUBMISSION_BYTES = 64 * 1024
_MAX_FINDINGS = 256


class CloudMisconfigValidator(Validator):
    name = "cloud_misconfig"
    requires_subprocess = False
    default_timeout_s = 1.0

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        expected, severities = _expected(config)
        must_include = _must_include_severities(config)
        min_findings = int(config.get("min_findings", len(expected)))
        allow_extra = bool(config.get("allow_extra", False))
        if min_findings < 1 or min_findings > len(expected):
            raise ValidatorConfigError(
                "cloud_misconfig: 'min_findings' must be between 1 and "
                "len(expected_findings)"
            )

        if len(submission.encode("utf-8")) > _MAX_SUBMISSION_BYTES:
            return ValidationResult(correct=False, details={"reason": "oversized"})

        try:
            parsed = json.loads(submission)
        except json.JSONDecodeError:
            return ValidationResult(correct=False, details={"reason": "not_json"})

        if not isinstance(parsed, list) or len(parsed) > _MAX_FINDINGS:
            return ValidationResult(correct=False, details={"reason": "shape"})

        try:
            submitted = _normalise(parsed)
        except _BadFinding as exc:
            return ValidationResult(
                correct=False, details={"reason": "bad_entry", "index": exc.index}
            )

        # de-duplicate exact pairs: a player listing the same finding
        # twice gains no extra credit.
        submitted_set: Set[Tuple[str, str]] = set(submitted)
        matched = submitted_set & expected

        if not allow_extra and submitted_set - expected:
            return ValidationResult(
                correct=False,
                details={
                    "reason": "unknown_findings",
                    "unknown_count": len(submitted_set - expected),
                },
            )

        if len(matched) < min_findings:
            return ValidationResult(
                correct=False,
                details={"reason": "insufficient", "matched": len(matched)},
            )

        if must_include:
            critical_keys = {
                key for key, sev in severities.items() if sev in must_include
            }
            missing_critical = critical_keys - matched
            if missing_critical:
                return ValidationResult(
                    correct=False,
                    details={
                        "reason": "missing_critical",
                        "missing_count": len(missing_critical),
                    },
                )

        return ValidationResult(correct=True, details={"matched": len(matched)})


class _BadFinding(Exception):
    def __init__(self, index: int) -> None:
        self.index = index
        super().__init__(index)


def _expected(
    config: Mapping[str, Any],
) -> Tuple[Set[Tuple[str, str]], dict[Tuple[str, str], str]]:
    expected_raw = config.get("expected_findings")
    if not isinstance(expected_raw, list) or not expected_raw or len(expected_raw) > _MAX_FINDINGS:
        raise ValidatorConfigError(
            "cloud_misconfig: 'expected_findings' must be a non-empty list "
            f"of <= {_MAX_FINDINGS} entries"
        )
    pairs: Set[Tuple[str, str]] = set()
    severities: dict[Tuple[str, str], str] = {}
    for index, entry in enumerate(expected_raw):
        if not isinstance(entry, dict):
            raise ValidatorConfigError(
                f"cloud_misconfig: expected_findings[{index}] must be an object"
            )
        resource = entry.get("resource")
        finding = entry.get("finding")
        severity = entry.get("severity", "info")
        if not isinstance(resource, str) or not resource:
            raise ValidatorConfigError(
                f"cloud_misconfig: expected_findings[{index}].resource missing"
            )
        if not isinstance(finding, str) or not finding:
            raise ValidatorConfigError(
                f"cloud_misconfig: expected_findings[{index}].finding missing"
            )
        if not isinstance(severity, str):
            raise ValidatorConfigError(
                f"cloud_misconfig: expected_findings[{index}].severity must be a string"
            )
        key = (resource, finding)
        pairs.add(key)
        severities[key] = severity
    return pairs, severities


def _must_include_severities(config: Mapping[str, Any]) -> Set[str]:
    raw = config.get("must_include_severities")
    if raw is None:
        return set()
    if not isinstance(raw, list) or not all(isinstance(s, str) for s in raw):
        raise ValidatorConfigError(
            "cloud_misconfig: 'must_include_severities' must be a list of strings"
        )
    return {str(s) for s in raw}


def _normalise(submitted: Iterable[Any]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for index, entry in enumerate(submitted):
        if not isinstance(entry, dict):
            raise _BadFinding(index)
        resource = entry.get("resource")
        finding = entry.get("finding")
        if not isinstance(resource, str) or not resource:
            raise _BadFinding(index)
        if not isinstance(finding, str) or not finding:
            raise _BadFinding(index)
        out.append((resource, finding))
    return out
