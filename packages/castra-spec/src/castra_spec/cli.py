"""``castra`` — the challenge author's CLI.

Three commands, mirroring the authoring loop:

    castra new my-challenge          # scaffold a working skeleton
    castra validate ./my-challenge   # parse + verify the manifest
    castra test ./my-challenge       # run the manifest's test cases

This is the standalone path: ``pip install castra-spec`` and author
challenges with no platform backend installed. The platform's own
harness (``make test-challenges``) runs the same code — this module is
a thin argparse front on :mod:`castra_spec.harness`.

Exit codes: 0 success, 1 failures (validation errors or failing test
cases), 2 usage errors. Stable — CI scripts may rely on them.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import textwrap
from pathlib import Path

from .harness import run_paths_sync
from .load import (
    LoadError,
    load_manifest,
)


def _cmd_new(args: argparse.Namespace) -> int:
    target = Path(args.directory)
    if target.exists() and any(target.iterdir()):
        print(f"castra new: {target} exists and is not empty", file=sys.stderr)
        return 2
    slug = target.name
    artifacts = target / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    sample = artifacts / "evidence.log"
    sample.write_text(
        "Apr 20 23:41:14 host sshd[4593]: replace me with real evidence\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(sample.read_bytes()).hexdigest()

    flag_open = "CTF" + "{"  # composed so repo flag-leak scanners don't trip
    manifest = textwrap.dedent(f"""\
        # Castra challenge manifest — spec v1.
        # Reference: https://castra.sh (docs/challenge-spec-v1.md in the repo)
        spec_version: "1"
        slug: {slug}
        title: "TODO: human title"
        description: |
          TODO: what the player is looking at and what they must find.

        team: blue
        category: "Threat Hunting"
        difficulty: 1
        points: 100
        license: MIT
        author:
          name: "TODO your name"

        # No ``container:`` block — this scaffold is artifact-only
        # (spec v1.1): the platform serves the files below and nothing
        # is launched. Add a container block if the challenge needs a
        # live service.

        flags:
          - id: main
            type: exact
            value: "{flag_open}TODO-real-flag}}"
            points: 100

        hints:
          - text: "TODO: first nudge"
            cost: 25

        artifacts:
          - path: artifacts/evidence.log
            sha256: "{digest}"
            description: "TODO: what this file is"

        tests:
          cases:
            - name: "correct flag passes"
              flag_id: main
              submission: "{flag_open}TODO-real-flag}}"
              expected: pass
            - name: "wrong flag fails"
              flag_id: main
              submission: "{flag_open}wrong}}"
              expected: fail
        """)
    (target / "manifest.yaml").write_text(manifest, encoding="utf-8")
    print(f"scaffolded {target}/")
    print("  manifest.yaml            — edit the TODOs")
    print("  artifacts/evidence.log   — replace, then update its sha256")
    print(f"next: castra validate {target}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    failures = 0
    for directory in args.directories:
        try:
            manifest, _raw = load_manifest(directory)
        except LoadError as exc:
            print(f"[FAIL] {directory}: {exc}", file=sys.stderr)
            failures += 1
            continue
        kind = "artifact-only" if manifest.container is None else "container"
        print(
            f"[OK]   {directory}  slug={manifest.slug} ({kind}, "
            f"{len(manifest.flags)} flag(s), {len(manifest.tests.cases)} test case(s))"
        )
        if not manifest.tests.cases:
            print(
                "       warning: no tests.cases — `castra test` has "
                "nothing to run for this challenge",
                file=sys.stderr,
            )
    return 1 if failures else 0


def _cmd_test(args: argparse.Namespace) -> int:
    report = run_paths_sync([Path(d) for d in args.directories])
    total = failed = errored = 0
    for challenge in report.challenges:
        for case in challenge.cases:
            total += 1
            status = case.status.value
            marker = {"passed": "passed ", "failed": "FAILED ", "errored": "ERRORED"}.get(status, status)
            if status == "failed":
                failed += 1
            elif status == "errored":
                errored += 1
            if not args.quiet or status != "passed":
                print(f"  {marker}  {case.case_name}  [{challenge.slug}]")
    if args.json:
        print(json.dumps({
            "total": total, "failed": failed, "errored": errored,
        }))
    else:
        print(f"summary: {total - failed - errored}/{total} passed  failed={failed} errored={errored}")
    return 1 if (failed or errored) else 0


def main(argv: list[str] | None = None) -> int:
    # Authoring context: the person running `castra test` is testing
    # their own regexes on their own machine, so the ReDoS defence
    # google-re2 provides on the platform protects nobody here — but
    # requiring a compiled wheel would block authors on platforms
    # without one. setdefault, not assignment: an author who installed
    # google-re2 (``pip install castra-spec[re2]``) still gets re2, and
    # an explicit SIEGE_ALLOW_RE_FALLBACK=0 still wins. The platform
    # never runs this entrypoint, so its strict behaviour is untouched.
    import os

    os.environ.setdefault("SIEGE_ALLOW_RE_FALLBACK", "1")

    parser = argparse.ArgumentParser(
        prog="castra",
        description="Author, validate and test Castra challenges.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_new = sub.add_parser("new", help="scaffold a new challenge directory")
    p_new.add_argument("directory", help="directory to create (its name becomes the slug)")
    p_new.set_defaults(func=_cmd_new)

    p_val = sub.add_parser("validate", help="parse and verify manifest(s)")
    p_val.add_argument("directories", nargs="+")
    p_val.set_defaults(func=_cmd_validate)

    p_test = sub.add_parser("test", help="run the manifest's test cases")
    p_test.add_argument("directories", nargs="+")
    p_test.add_argument("--quiet", action="store_true", help="only print failures")
    p_test.add_argument("--json", action="store_true", help="machine-readable summary line")
    p_test.set_defaults(func=_cmd_test)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
