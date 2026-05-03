"""Validator plugin contract.

Phase 8 introduces a pluggable validator system. Each ``Flag`` declared
in a manifest carries a ``type`` (e.g. ``exact``, ``regex``,
``multi_part``) that names a validator plugin. The platform discovers
plugins via the ``bluerange.validators`` entry-point group; the v1
first-party set ships under that same mechanism so external authors
exercise an identical code path.

This module is the **public contract** every plugin author depends on.
Keeping it inside ``bluerange-spec`` (one-way dep into the platform)
means a plugin package never imports ``app.*`` and stays installable
without the platform present.

Design constraints (CLAUDE.md §1.4, §3, §15):
- Validators are pure: no DB session, no audit service, no I/O beyond
  the read-only ``artifact_dir`` provided in the context.
- Validators must respect ``default_timeout_s``. The platform also
  enforces an outer ``asyncio.timeout`` per call as defence-in-depth.
- ``requires_subprocess=True`` validators run inside a
  ``resource.setrlimit``-bounded subprocess pool managed by the
  platform (Phase 8 sandbox). Pure-Python validators bypass it.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Mapping, Optional


@dataclass(frozen=True)
class ValidationContext:
    """Read-only execution context handed to a validator.

    ``artifact_dir`` — when non-None, points at a directory whose mode
    bits are ``0555`` (or that is mounted ``ro``). Validators may read
    files inside it but must not mutate them. The platform copies
    artefacts into an isolated location per-submission rather than
    handing over the canonical challenge directory, so a buggy
    validator cannot contaminate state shared with other submissions.

    ``submission_metadata`` is a free-form dict the platform populates
    with non-secret hints (e.g. ``submission_id``). It is **not** a
    channel for a validator to talk back — return values flow through
    :class:`ValidationResult`.
    """

    flag_id: str
    challenge_slug: str
    artifact_dir: Optional[Path] = None
    submission_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of a single validator call.

    ``correct`` is the only field the platform consults to award points
    in v1. ``partial`` and ``details`` are reserved for stateful
    validators (e.g. multi-part progress, chain-of-custody) introduced
    in Phase 10/11; preserving them now keeps the contract stable.
    """

    correct: bool
    partial: bool = False
    details: Mapping[str, Any] = field(default_factory=dict)


class ValidatorError(Exception):
    """Base class for validator-domain errors."""


class ValidatorConfigError(ValidatorError):
    """Validator received an invalid ``config`` mapping."""


class ValidatorTimeoutError(ValidatorError):
    """Validator exceeded its execution budget.

    Raised by the platform's sandbox layer, not by validators
    themselves. Plugins that need to express "this took too long"
    should return ``ValidationResult(correct=False)``.
    """


class Validator(abc.ABC):
    """Plugin contract.

    Subclasses are constructed once at registry boot and reused across
    submissions, so they must be **stateless** with respect to a single
    user / submission. Per-submission state lives in the
    :class:`ValidationContext` and the return value.

    Class attributes:
        ``name`` — entry-point name; must equal the manifest
            ``flag.type`` string. Lowercase letters, digits, and
            underscores only.
        ``requires_subprocess`` — when True, the platform runs
            :meth:`validate` inside the resource-limited subprocess
            pool. False for pure-Python validators (the v1 built-ins).
        ``requires_artifacts`` — when True, the platform stages a
            read-only copy of the challenge directory and populates
            :attr:`ValidationContext.artifact_dir`. Otherwise
            ``artifact_dir`` is ``None`` and the validator must operate
            on the submission + config alone.
        ``default_timeout_s`` — wall-clock seconds the platform
            enforces with ``asyncio.timeout`` around the call.
    """

    name: ClassVar[str]
    requires_subprocess: ClassVar[bool] = False
    requires_artifacts: ClassVar[bool] = False
    default_timeout_s: ClassVar[float] = 2.0

    @abc.abstractmethod
    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        """Check ``submission`` against the flag described by ``config``.

        Implementations must not raise on a wrong-but-well-formed
        submission — return ``ValidationResult(correct=False)``
        instead. Raise :class:`ValidatorConfigError` only when
        ``config`` is structurally invalid (a programming error, not a
        user error).
        """


__all__ = [
    "Validator",
    "ValidatorConfigError",
    "ValidatorError",
    "ValidatorTimeoutError",
    "ValidationContext",
    "ValidationResult",
]
