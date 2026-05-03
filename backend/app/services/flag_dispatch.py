"""Submission → validator dispatch.

Sits between :mod:`flag_submission` (which owns the audit + scoring +
persistence flow) and :mod:`validator_registry` (which owns plugin
discovery). This module's job is:

1. Decide which validator(s) a submission should be checked against
   for a given :class:`~app.models.Challenge`.
2. Dispatch through :func:`validator_sandbox.run_validator` so the
   timeout guard always applies.
3. Translate the validator's :class:`ValidationResult` into the
   "correct / not correct" boolean the submission flow needs.

Two challenge shapes are supported:

- **v1 challenges** (Phase 7+) declare per-flag rows in
  ``challenge_flags``. The dispatch iterates them and accepts the
  first match; the matched ``flag_id`` is returned for downstream
  audit context.
- **Legacy challenges** keep the cleartext-free ``challenges.flag_hash``
  column. Dispatch routes through the same ``exact`` validator using
  that hash as the validator config.

The semantic decision to return after the first matching flag (rather
than aggregating per-flag captures) is intentionally narrow for
Phase 8 — multi-flag scoring is Phase 11. Keeping the contract
single-flag here means we don't ship a half-finished scoring
mechanism that future work will rewrite.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from bluerange_spec import ValidationContext

from app.models import Challenge
from app.services.validator_registry import (
    UnknownValidator,
    ValidatorRegistry,
    get_registry,
)
from app.services.validator_sandbox import readonly_artifact_dir, run_validator


@dataclass(frozen=True)
class DispatchResult:
    correct: bool
    flag_id: Optional[str] = None
    validator_name: Optional[str] = None


_LEGACY_FLAG_ID = "legacy"
_LEGACY_VALIDATOR = "exact"


async def dispatch_submission(
    submission: str,
    challenge: Challenge,
    *,
    registry: Optional[ValidatorRegistry] = None,
) -> DispatchResult:
    """Run ``submission`` against the challenge's flag definitions.

    The function is pure with respect to the platform's persistence
    layer: it inspects the SQLAlchemy model row but never writes to
    the DB. Audit emission stays in :mod:`flag_submission`.
    """

    reg = registry or get_registry()
    candidate = submission.strip()

    if challenge.flag_definitions:
        return await _dispatch_v1(candidate, challenge, reg)
    return await _dispatch_legacy(candidate, challenge, reg)


async def _dispatch_v1(
    submission: str,
    challenge: Challenge,
    registry: ValidatorRegistry,
) -> DispatchResult:
    for flag in challenge.flag_definitions:
        try:
            validator = registry.get(flag.flag_type)
        except UnknownValidator:
            # Skip flags whose validator plugin isn't installed; the
            # admin UI surfaces missing plugins via the registry's
            # introspection endpoint (Phase 12). Treating an unknown
            # validator as a hard failure here would lock out every
            # submission on a partially-misconfigured deployment.
            continue
        config = dict(flag.config or {})
        if flag.flag_type == "exact" and "value_hash" not in config:
            config["value_hash"] = flag.value_hash or ""

        result = await _run_with_optional_artifacts(
            validator, submission, config, challenge, flag.flag_id
        )
        if result.correct:
            return DispatchResult(
                correct=True,
                flag_id=flag.flag_id,
                validator_name=validator.name,
            )
    return DispatchResult(correct=False)


async def _run_with_optional_artifacts(
    validator,
    submission: str,
    config: dict,
    challenge: Challenge,
    flag_id: str,
):
    """Wrap :func:`run_validator` with a read-only artefact copy when needed.

    Validators that declare ``requires_artifacts=True`` (sigma / yara
    in Phase 10) get ``ValidationContext.artifact_dir`` populated with
    a path inside a per-call temp tree whose mode bits are 0555 / 0444.
    Pure-Python validators see ``artifact_dir=None`` to make it
    obvious they have no business reading the FS.
    """

    if not getattr(validator, "requires_artifacts", False):
        context = ValidationContext(flag_id=flag_id, challenge_slug=challenge.slug)
        return await run_validator(validator, submission, config, context)

    source = challenge.source_path
    if not source:
        # Validator demands artefacts but the challenge has no
        # canonical source path (legacy seed). Treat as a hard "wrong
        # submission" rather than raising — the dispatch loop must
        # continue trying any other configured flags.
        return _wrong_result()

    async with readonly_artifact_dir(Path(source)) as ro_path:
        context = ValidationContext(
            flag_id=flag_id,
            challenge_slug=challenge.slug,
            artifact_dir=ro_path,
        )
        return await run_validator(validator, submission, config, context)


def _wrong_result():
    from bluerange_spec import ValidationResult

    return ValidationResult(correct=False)


async def _dispatch_legacy(
    submission: str,
    challenge: Challenge,
    registry: ValidatorRegistry,
) -> DispatchResult:
    if not challenge.flag_hash:
        return DispatchResult(correct=False)
    validator = registry.get(_LEGACY_VALIDATOR)
    config = {"value_hash": challenge.flag_hash, "case_sensitive": True}
    context = ValidationContext(
        flag_id=_LEGACY_FLAG_ID,
        challenge_slug=challenge.slug,
    )
    result = await run_validator(validator, submission, config, context)
    return DispatchResult(
        correct=result.correct,
        flag_id=_LEGACY_FLAG_ID if result.correct else None,
        validator_name=_LEGACY_VALIDATOR if result.correct else None,
    )
