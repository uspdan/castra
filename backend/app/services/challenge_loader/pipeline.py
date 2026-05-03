"""Top-level orchestration: discover → validate → (optionally) upsert.

The CLI in :mod:`app.tools.load_challenges` is a thin shell over
:func:`run`. Tests exercise this module directly with an in-memory list
of paths.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bluerange_spec import (
    ManifestNotFound,
    ManifestParseError,
    ManifestValidationError,
)

from .discovery import discover
from .errors import ArtifactMismatch, LoaderError, UnknownProfile
from .single import LoadedManifest, load_directory
from .upsert import UpsertOutcome, upsert_manifest


class LoadStatus(str, enum.Enum):
    LOADED = "loaded"
    UNCHANGED = "unchanged"
    PENDING_REVIEW = "pending_review"
    INVALID = "invalid"
    ARTIFACT_MISMATCH = "artifact_mismatch"
    UNKNOWN_PROFILE = "unknown_profile"


@dataclass
class LoadOutcome:
    directory: Path
    slug: Optional[str]
    status: LoadStatus
    detail: str = ""
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in (
            LoadStatus.LOADED,
            LoadStatus.UNCHANGED,
            LoadStatus.PENDING_REVIEW,
        )


@dataclass
class LoadReport:
    outcomes: List[LoadOutcome] = field(default_factory=list)

    @property
    def failure_count(self) -> int:
        return sum(1 for o in self.outcomes if not o.ok)

    @property
    def success_count(self) -> int:
        return sum(1 for o in self.outcomes if o.ok)


async def run(
    roots: Iterable[Path | str],
    *,
    db: Optional[AsyncSession] = None,
    dry_run: bool = False,
) -> LoadReport:
    """Discover manifests under each root and process each one.

    When ``dry_run`` is true, validation is performed but no DB writes
    happen — ``db`` is allowed to be ``None`` in that mode. When
    ``dry_run`` is false, ``db`` is required and the caller controls
    when to commit.
    """

    if not dry_run and db is None:
        raise ValueError("db is required when dry_run is False")

    report = LoadReport()
    for found in discover(roots):
        outcome = await _process_one(found.directory, db=db, dry_run=dry_run)
        report.outcomes.append(outcome)
    return report


async def _process_one(
    directory: Path,
    *,
    db: Optional[AsyncSession],
    dry_run: bool,
) -> LoadOutcome:
    try:
        loaded = load_directory(directory)
    except ManifestNotFound as exc:
        return LoadOutcome(directory=directory, slug=None, status=LoadStatus.INVALID, detail=str(exc))
    except ManifestParseError as exc:
        return LoadOutcome(directory=directory, slug=None, status=LoadStatus.INVALID, detail=str(exc))
    except ManifestValidationError as exc:
        return LoadOutcome(
            directory=directory,
            slug=None,
            status=LoadStatus.INVALID,
            detail=_format_validation(exc),
        )
    except UnknownProfile as exc:
        return LoadOutcome(
            directory=directory,
            slug=None,
            status=LoadStatus.UNKNOWN_PROFILE,
            detail=str(exc),
        )
    except ArtifactMismatch as exc:
        return LoadOutcome(
            directory=directory,
            slug=None,
            status=LoadStatus.ARTIFACT_MISMATCH,
            detail=str(exc),
        )
    except LoaderError as exc:
        return LoadOutcome(
            directory=directory,
            slug=None,
            status=LoadStatus.INVALID,
            detail=str(exc),
        )

    slug = loaded.manifest.slug
    if dry_run:
        return LoadOutcome(
            directory=directory,
            slug=slug,
            status=LoadStatus.LOADED,
            warnings=list(loaded.warnings),
        )

    assert db is not None  # narrowed by the dry_run check in run()
    upsert: UpsertOutcome = await upsert_manifest(db, loaded)
    if upsert.created or upsert.digest_changed:
        return LoadOutcome(
            directory=directory,
            slug=slug,
            status=LoadStatus.PENDING_REVIEW,
            warnings=list(loaded.warnings),
        )
    return LoadOutcome(
        directory=directory,
        slug=slug,
        status=LoadStatus.UNCHANGED,
        warnings=list(loaded.warnings),
    )


def _format_validation(exc: ManifestValidationError) -> str:
    parts = [str(exc)]
    for err in exc.errors:
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"  - {loc}: {err.get('msg')}")
    return "\n".join(parts)
