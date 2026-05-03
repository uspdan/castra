"""CLI entrypoint for the offline challenge test harness.

Usage::

    python -m app.tools.test_harness [PATH ...]
    python -m app.tools.test_harness --json [PATH ...]
    python -m app.tools.test_harness --filter slug-glob [PATH ...]

When invoked with no PATH, defaults to ``examples/challenges``
relative to the current working directory.

Exit codes::

    0 — every test case passed (or no test cases declared anywhere)
    1 — at least one case failed or errored
    2 — operational failure (manifest unparseable, validator plugin
        unavailable, unexpected exception)

The CLI is deliberately read-only: it never touches the platform DB,
spawns no orchestrator instances, and applies no migrations. Same
binary runs locally and in CI.
"""

from __future__ import annotations

import argparse
import asyncio
import fnmatch
import json
import sys
from pathlib import Path
from typing import Sequence

from app.services.test_harness import (
    CaseStatus,
    HarnessReport,
    run_paths,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="test_harness",
        description=(
            "Run challenge manifest test cases through the validator "
            "registry without standing up the platform."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Challenge directories or roots to walk. Defaults to "
        "examples/challenges relative to CWD.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable report on stdout.",
    )
    parser.add_argument(
        "--filter",
        metavar="GLOB",
        default=None,
        help="Only run challenges whose slug matches GLOB (fnmatch syntax).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-case output; print only the summary line.",
    )
    return parser


def _resolve_paths(raw: Sequence[str]) -> list[Path]:
    if raw:
        return [Path(p) for p in raw]
    default = Path("examples/challenges")
    return [default]


def _filter_report(report: HarnessReport, glob: str | None) -> HarnessReport:
    if not glob:
        return report
    keep = [c for c in report.challenges if fnmatch.fnmatch(c.slug, glob)]
    return HarnessReport(challenges=keep)


def _exit_code(report: HarnessReport) -> int:
    if not report.challenges:
        return 0
    counts = report.case_counts
    if counts["errored"] > 0:
        # Errored = validator-side / loader-side / plugin-missing problem;
        # operational, not a test failure. Distinguishing helps CI
        # surface infrastructure regressions separately from genuinely
        # broken challenges.
        if counts["failed"] == 0 and all(
            c.load_error is None for c in report.challenges
        ):
            return 2
    if counts["failed"] > 0 or counts["errored"] > 0:
        return 1
    return 0


def _print_human(report: HarnessReport, *, quiet: bool) -> None:
    counts = report.case_counts
    for outcome in report.challenges:
        status_word = "OK" if outcome.all_passed else "FAIL"
        if outcome.load_error:
            print(f"[{status_word}] {outcome.slug}  load error: {outcome.load_error}")
            continue
        if not outcome.cases:
            print(f"[--] {outcome.slug}  (no test cases)")
            continue
        print(f"[{status_word}] {outcome.slug}  ({len(outcome.cases)} cases)")
        if quiet:
            continue
        for case in outcome.cases:
            actual = (
                ""
                if case.actual_correct is None
                else f"actual={case.actual_correct} "
            )
            tail = case.error or ""
            print(
                f"    {case.status.value:<8} {case.case_name}  "
                f"flag={case.flag_id} expected={case.expected} {actual}{tail}".rstrip()
            )
    total = sum(counts.values())
    print(
        f"summary: {counts['passed']}/{total} passed  "
        f"failed={counts['failed']} errored={counts['errored']}"
    )


def _to_json_report(report: HarnessReport) -> dict:
    return {
        "challenges": [
            {
                "slug": c.slug,
                "directory": str(c.directory),
                "all_passed": c.all_passed,
                "load_error": c.load_error,
                "cases": [
                    {
                        "name": case.case_name,
                        "flag_id": case.flag_id,
                        "expected": case.expected,
                        "status": case.status.value,
                        "actual_correct": case.actual_correct,
                        "error": case.error,
                    }
                    for case in c.cases
                ],
            }
            for c in report.challenges
        ],
        "case_counts": report.case_counts,
        "all_passed": report.all_passed,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    paths = _resolve_paths(args.paths)

    try:
        report = asyncio.run(run_paths(paths))
    except Exception as exc:  # noqa: BLE001 — top-level CLI guard
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    report = _filter_report(report, args.filter)

    if args.json:
        json.dump(_to_json_report(report), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        _print_human(report, quiet=args.quiet)

    return _exit_code(report)


if __name__ == "__main__":  # pragma: no cover — exercised via CLI
    sys.exit(main())
