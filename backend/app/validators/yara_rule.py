"""YARA rule validator (malware-triage challenges).

The submission is a YARA rule. The validator compiles the rule with
``yara-python``, scans every file in a fixture directory under
``artifact_dir``, and verifies the rule fires on (and only on) the
expected positive samples.

Submission format
-----------------

A single YARA rule (or rule set). The rule's *name* is irrelevant —
the validator scans every sample regardless of which rule fires.

Config
------

::

    {
      "samples_dir": "samples",          # directory under artifact_dir
      "expected_matches": ["evil1.bin", "evil2.bin"],
      "expected_no_match": ["clean1.bin", "clean2.bin"],
      "max_sample_bytes": 1048576        # optional, default 1 MiB
    }

Decision rules
--------------

* Every file in ``expected_matches`` must produce at least one rule
  match.
* Every file in ``expected_no_match`` must produce zero rule matches.
* The rule must compile cleanly. Compilation errors return
  ``correct=False`` with a structured ``reason``.
* Files larger than ``max_sample_bytes`` are skipped (treated as no
  match) to bound the validator's worst-case I/O — challenge authors
  should keep fixtures small.

The validator runs inside the subprocess sandbox; ``yara-python``'s
linked libyara may use a fair bit of memory on pathological rules,
so the sandbox's ``RLIMIT_AS`` enforces an upper bound.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Mapping

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


_MAX_RULE_BYTES = 64 * 1024
_MAX_FIXTURE_FILES = 64
_DEFAULT_MAX_SAMPLE_BYTES = 1 * 1024 * 1024  # 1 MiB


class YaraRuleValidator(Validator):
    name = "yara_rule"
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
                "yara_rule: validator requires artifact_dir; the platform "
                "did not stage challenge artefacts"
            )
        if len(submission.encode("utf-8")) > _MAX_RULE_BYTES:
            return ValidationResult(correct=False, details={"reason": "oversized_rule"})

        samples_dir = _samples_dir(context.artifact_dir, config)
        positives = _string_list(config, "expected_matches")
        negatives = _string_list(config, "expected_no_match", required=False)
        max_sample_bytes = int(config.get("max_sample_bytes", _DEFAULT_MAX_SAMPLE_BYTES))
        if max_sample_bytes <= 0 or max_sample_bytes > 16 * 1024 * 1024:
            raise ValidatorConfigError(
                "yara_rule: 'max_sample_bytes' must be between 1 and 16 MiB"
            )

        try:
            import yara  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover — dep guaranteed in prod
            raise ValidatorConfigError(
                f"yara_rule: yara-python not installed: {exc}"
            ) from exc

        try:
            compiled = yara.compile(source=submission)
        except yara.SyntaxError as exc:
            return ValidationResult(
                correct=False,
                details={"reason": "rule_compile_error", "error": str(exc)[:200]},
            )

        for filename in positives:
            ok, reason = _scan_file(
                compiled, samples_dir, filename, max_sample_bytes, expect_match=True
            )
            if not ok:
                return ValidationResult(
                    correct=False,
                    details={"reason": reason, "file": filename},
                )

        for filename in negatives:
            ok, reason = _scan_file(
                compiled, samples_dir, filename, max_sample_bytes, expect_match=False
            )
            if not ok:
                return ValidationResult(
                    correct=False,
                    details={"reason": reason, "file": filename},
                )

        return ValidationResult(
            correct=True,
            details={"matched": list(positives), "no_match": list(negatives)},
        )


def _samples_dir(artifact_dir: Path, config: Mapping[str, Any]) -> Path:
    raw = config.get("samples_dir", "samples")
    if not isinstance(raw, str) or not raw:
        raise ValidatorConfigError(
            "yara_rule: 'samples_dir' must be a non-empty string"
        )
    if "/" in raw or ".." in raw or raw.startswith("."):
        raise ValidatorConfigError(
            "yara_rule: 'samples_dir' must be a single subdirectory name"
        )
    return artifact_dir / raw


def _string_list(
    config: Mapping[str, Any], key: str, *, required: bool = True
) -> List[str]:
    raw = config.get(key)
    if raw is None:
        if required:
            raise ValidatorConfigError(f"yara_rule: '{key}' is required")
        return []
    if not isinstance(raw, list) or len(raw) > _MAX_FIXTURE_FILES:
        raise ValidatorConfigError(
            f"yara_rule: '{key}' must be a list of <= {_MAX_FIXTURE_FILES} filenames"
        )
    out: List[str] = []
    for item in raw:
        if not isinstance(item, str) or not item:
            raise ValidatorConfigError(
                f"yara_rule: '{key}' entries must be non-empty strings"
            )
        if "/" in item or ".." in item or item.startswith("."):
            raise ValidatorConfigError(
                f"yara_rule: '{key}' entry {item!r} must be a bare filename"
            )
        out.append(item)
    return out


def _scan_file(
    compiled,
    samples_dir: Path,
    filename: str,
    max_bytes: int,
    *,
    expect_match: bool,
) -> tuple[bool, str]:
    path = samples_dir / filename
    if not path.exists() or not path.is_file():
        return False, "fixture_missing"
    if path.stat().st_size > max_bytes:
        # Author is responsible for keeping fixtures small. We refuse
        # to scan oversize files rather than silently truncating.
        return False, "fixture_oversize"
    try:
        data = path.read_bytes()
    except OSError:
        return False, "fixture_unreadable"
    try:
        matches = compiled.match(data=data)
    except Exception as exc:  # noqa: BLE001 — yara's own error class is dynamic
        return False, f"scan_error:{type(exc).__name__}"
    matched = bool(matches)
    if expect_match and not matched:
        return False, "expected_match_no_match"
    if not expect_match and matched:
        return False, "expected_no_match_matched"
    return True, ""
