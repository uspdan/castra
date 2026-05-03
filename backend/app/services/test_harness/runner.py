"""Test-harness runner: dispatch manifest TestCases through validators.

Each :class:`bluerange_spec.TestCase` carries a ``flag_id``, a
``submission`` string, and an ``expected ∈ {"pass", "fail"}``
discriminator. The runner:

1. Loads the manifest (via :func:`bluerange_spec.load_manifest`).
2. Resolves ``case.flag_id`` to the matching :class:`Flag` model.
3. Translates the flag into dispatch args via :func:`flag_to_dispatch`
   — the same path the loader uses to write
   ``challenge_flags`` rows, so harness behaviour matches the
   production submission path bit-for-bit.
4. Builds a :class:`ValidationContext`. For
   ``requires_artifacts=True`` validators the context's
   ``artifact_dir`` points at a per-call read-only copy of the
   challenge directory (same primitive the API uses).
5. Dispatches through :func:`run_validator`, which transparently
   spawns the resource-limited subprocess for
   ``requires_subprocess=True`` validators.
6. Compares ``result.correct`` to the case's ``expected`` and emits
   a structured outcome.

The harness has no DB / Redis dependency. It can run from any
directory, in CI, or via the ``app.tools.test_harness`` CLI.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Sequence

from bluerange_spec import (
    ChallengeManifest,
    ManifestNotFound,
    TestCase,
    ValidationContext,
    ValidatorError,
    load_manifest,
)

from app.services.challenge_loader.flag_mapping import (
    FlagDispatchArgs,
    flag_to_dispatch,
)
from app.services.validator_registry import (
    UnknownValidator,
    ValidatorRegistry,
    get_registry,
)
from app.services.validator_sandbox import readonly_artifact_dir, run_validator


class CaseStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CaseOutcome:
    """Result of a single test case run."""

    case_name: str
    flag_id: str
    expected: str
    status: CaseStatus
    actual_correct: Optional[bool] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class HarnessOutcome:
    """Aggregate result for one challenge directory."""

    slug: str
    directory: Path
    cases: List[CaseOutcome] = field(default_factory=list)
    load_error: Optional[str] = None

    @property
    def all_passed(self) -> bool:
        if self.load_error is not None:
            return False
        return all(c.status == CaseStatus.PASSED for c in self.cases)


@dataclass(frozen=True)
class HarnessReport:
    """Aggregate result across one or more challenge roots."""

    challenges: List[HarnessOutcome]

    @property
    def all_passed(self) -> bool:
        return all(c.all_passed for c in self.challenges)

    @property
    def case_counts(self) -> dict[str, int]:
        counts = {s.value: 0 for s in CaseStatus}
        for outcome in self.challenges:
            for case in outcome.cases:
                counts[case.status.value] += 1
        return counts


# ---------------------------------------------------------------------------
# Single-case dispatch
# ---------------------------------------------------------------------------
async def run_case(
    case: TestCase,
    *,
    flag_args: FlagDispatchArgs,
    challenge_slug: str,
    challenge_dir: Path,
    registry: Optional[ValidatorRegistry] = None,
) -> CaseOutcome:
    """Dispatch a single :class:`TestCase` and return a :class:`CaseOutcome`.

    Pure-async — never raises. Validator config / runtime errors are
    captured into ``CaseOutcome.error`` with status
    :attr:`CaseStatus.ERRORED`. The expected/actual comparison is the
    only path that yields :attr:`CaseStatus.PASSED` /
    :attr:`CaseStatus.FAILED`.
    """

    reg = registry or get_registry()
    try:
        validator = reg.get(flag_args.flag_type)
    except UnknownValidator as exc:
        return CaseOutcome(
            case_name=case.name,
            flag_id=case.flag_id,
            expected=case.expected,
            status=CaseStatus.ERRORED,
            error=f"validator plugin not installed: {exc}",
        )

    config = dict(flag_args.config)
    if flag_args.flag_type == "exact" and "value_hash" not in config:
        # The on-DB row stores value_hash separately; the harness has
        # to populate it into config because dispatch_submission's
        # API-path does the same thing and ExactValidator looks for
        # it under "value_hash".
        config["value_hash"] = flag_args.value_hash or ""

    try:
        if getattr(validator, "requires_artifacts", False):
            async with readonly_artifact_dir(challenge_dir) as ro:
                ctx = ValidationContext(
                    flag_id=flag_args.flag_id,
                    challenge_slug=challenge_slug,
                    artifact_dir=ro,
                )
                result = await run_validator(validator, case.submission, config, ctx)
        else:
            ctx = ValidationContext(
                flag_id=flag_args.flag_id,
                challenge_slug=challenge_slug,
            )
            result = await run_validator(validator, case.submission, config, ctx)
    except ValidatorError as exc:
        return CaseOutcome(
            case_name=case.name,
            flag_id=case.flag_id,
            expected=case.expected,
            status=CaseStatus.ERRORED,
            error=f"{type(exc).__name__}: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 — surface runtime failures
        return CaseOutcome(
            case_name=case.name,
            flag_id=case.flag_id,
            expected=case.expected,
            status=CaseStatus.ERRORED,
            error=f"{type(exc).__name__}: {exc}",
        )

    expected_correct = case.expected == "pass"
    matched = result.correct is expected_correct
    return CaseOutcome(
        case_name=case.name,
        flag_id=case.flag_id,
        expected=case.expected,
        status=CaseStatus.PASSED if matched else CaseStatus.FAILED,
        actual_correct=result.correct,
    )


# ---------------------------------------------------------------------------
# Per-challenge orchestration
# ---------------------------------------------------------------------------
async def run_challenge(
    directory: Path | str,
    *,
    registry: Optional[ValidatorRegistry] = None,
) -> HarnessOutcome:
    """Run every test case declared by the manifest at ``directory``."""

    directory = Path(directory)
    try:
        manifest, _raw = load_manifest(directory)
    except Exception as exc:  # noqa: BLE001 — surface load failures
        return HarnessOutcome(
            slug=directory.name,
            directory=directory,
            cases=[],
            load_error=f"{type(exc).__name__}: {exc}",
        )

    if not manifest.tests.cases:
        return HarnessOutcome(slug=manifest.slug, directory=directory, cases=[])

    flag_index = _index_flags(manifest)
    outcomes: List[CaseOutcome] = []
    for case in manifest.tests.cases:
        args = flag_index.get(case.flag_id)
        if args is None:
            outcomes.append(
                CaseOutcome(
                    case_name=case.name,
                    flag_id=case.flag_id,
                    expected=case.expected,
                    status=CaseStatus.ERRORED,
                    error=f"flag_id {case.flag_id!r} not declared in manifest",
                )
            )
            continue
        outcomes.append(
            await run_case(
                case,
                flag_args=args,
                challenge_slug=manifest.slug,
                challenge_dir=directory,
                registry=registry,
            )
        )

    return HarnessOutcome(
        slug=manifest.slug, directory=directory, cases=outcomes
    )


# ---------------------------------------------------------------------------
# Multi-root walker
# ---------------------------------------------------------------------------
async def run_paths(
    roots: Sequence[Path | str],
    *,
    registry: Optional[ValidatorRegistry] = None,
) -> HarnessReport:
    """Walk ``roots`` and run every challenge directory found.

    A "challenge directory" is any directory containing one of the
    manifest filenames recognised by :func:`bluerange_spec.load_manifest`.
    Directories without a manifest are skipped silently — that lets
    callers point the harness at a parent directory that mixes
    challenges with other files.
    """

    discovered = sorted(_discover_challenge_dirs(roots))
    outcomes: List[HarnessOutcome] = []
    for directory in discovered:
        outcomes.append(await run_challenge(directory, registry=registry))
    return HarnessReport(challenges=outcomes)


def _index_flags(manifest: ChallengeManifest) -> dict[str, FlagDispatchArgs]:
    out: dict[str, FlagDispatchArgs] = {}
    for flag in manifest.flags:
        out[flag.id] = flag_to_dispatch(flag)
    return out


_MANIFEST_NAMES = ("manifest.yaml", "manifest.yml", "manifest.json")


def _discover_challenge_dirs(roots: Sequence[Path | str]) -> list[Path]:
    dirs: set[Path] = set()
    for raw in roots:
        root = Path(raw)
        if not root.exists():
            continue
        if root.is_file():
            if root.name in _MANIFEST_NAMES:
                dirs.add(root.parent.resolve())
            continue
        # If the root *is* a challenge directory, include it directly
        # rather than walking its children.
        if any((root / name).exists() for name in _MANIFEST_NAMES):
            dirs.add(root.resolve())
            continue
        for child in root.iterdir():
            if child.is_dir() and any(
                (child / name).exists() for name in _MANIFEST_NAMES
            ):
                dirs.add(child.resolve())
    return list(dirs)


# ---------------------------------------------------------------------------
# Sync convenience wrapper
# ---------------------------------------------------------------------------
def run_paths_sync(
    roots: Sequence[Path | str],
    *,
    registry: Optional[ValidatorRegistry] = None,
) -> HarnessReport:
    """Synchronous wrapper around :func:`run_paths` for the CLI."""

    return asyncio.run(run_paths(roots, registry=registry))
