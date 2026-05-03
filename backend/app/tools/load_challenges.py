"""CLI entrypoint for the challenge loader.

Usage::

    python -m app.tools.load_challenges --dry-run [PATH ...]
    python -m app.tools.load_challenges --apply   [PATH ...]

When invoked with no PATH, defaults to ``examples/challenges`` relative
to the current working directory.

Exit codes::

    0 — every discovered manifest validated (and applied, if --apply)
    1 — at least one manifest failed validation or artifact integrity
    2 — operational failure (DB unreachable, unexpected exception)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Sequence

from app.database import async_session
from app.services.challenge_loader import LoadReport, LoadStatus, run


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="load_challenges",
        description="Validate and (optionally) load v1 challenge manifests.",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manifests; do not touch the database.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Validate and upsert manifests into the challenges DB.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable lines.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Challenge directories or roots to scan (default: examples/challenges).",
    )
    return parser


async def _run_async(paths: List[Path], dry_run: bool) -> LoadReport:
    if dry_run:
        return await run(paths, db=None, dry_run=True)
    async with async_session() as session:
        report = await run(paths, db=session, dry_run=False)
        if report.failure_count == 0:
            await session.commit()
        else:
            await session.rollback()
        return report


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    paths = [Path(p) for p in args.paths] or [Path("examples/challenges")]

    try:
        report = asyncio.run(_run_async(paths, dry_run=args.dry_run))
    except Exception as exc:  # pragma: no cover — top-level safety net
        sys.stderr.write(f"load_challenges: operational failure: {exc}\n")
        return 2

    _emit(report, as_json=args.json)
    return 0 if report.failure_count == 0 else 1


def _emit(report: LoadReport, *, as_json: bool) -> None:
    if as_json:
        sys.stdout.write(json.dumps(_serialise(report), indent=2) + "\n")
        return
    for outcome in report.outcomes:
        line = f"[{outcome.status.value}] {outcome.directory} ({outcome.slug or '-'})"
        sys.stdout.write(line + "\n")
        if outcome.detail:
            for detail_line in outcome.detail.splitlines():
                sys.stdout.write(f"    {detail_line}\n")
        for warning in outcome.warnings:
            sys.stdout.write(f"    warning: {warning}\n")
    sys.stdout.write(
        f"\n{report.success_count} ok, {report.failure_count} failed\n"
    )


def _serialise(report: LoadReport) -> dict:
    return {
        "success_count": report.success_count,
        "failure_count": report.failure_count,
        "outcomes": [
            {
                "directory": str(o.directory),
                "slug": o.slug,
                "status": o.status.value,
                "detail": o.detail,
                "warnings": list(o.warnings),
            }
            for o in report.outcomes
        ],
    }


if __name__ == "__main__":
    sys.exit(main())
