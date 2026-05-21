#!/usr/bin/env python3
"""seal-flags — move cleartext flags out of every ``challenge.json``.

For each ``challenges/<slug>/challenge.json``:
  * read the ``flag`` field
  * record the slug → cleartext mapping in ``secrets/flags.json``
  * delete the ``flag`` field from the public JSON

After this script runs:
  * the public repo no longer contains any cleartext ``CTF{REDACTED}``
  * ``secrets/flags.json`` (gitignored) holds the mapping
  * ``scripts/seed_challenges.py`` merges from the secrets file
    before POSTing to the admin endpoint

Idempotent. Re-running just refreshes the mapping with whatever's
currently in the public files (so if a flag was rotated upstream,
re-run this to capture the new value before stripping).

Usage:
    scripts/seal-flags.py            # strip + write secrets/flags.json
    scripts/seal-flags.py --dry-run  # report what would change
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHALLENGES_DIR = ROOT / "challenges"
SECRETS_DIR = ROOT / "secrets"
SECRETS_FILE = SECRETS_DIR / "flags.json"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="report what would change without writing")
    args = p.parse_args()

    if not CHALLENGES_DIR.is_dir():
        sys.exit(f"error: {CHALLENGES_DIR} not found")

    SECRETS_DIR.mkdir(exist_ok=True)
    existing: dict[str, str] = {}
    if SECRETS_FILE.exists():
        existing = json.loads(SECRETS_FILE.read_text())

    sealed = dict(existing)
    stripped: list[str] = []
    untouched: list[str] = []

    for manifest_path in sorted(CHALLENGES_DIR.glob("*/challenge.json")):
        slug = manifest_path.parent.name
        if slug.startswith("_"):
            continue
        manifest = json.loads(manifest_path.read_text())
        flag = manifest.get("flag")
        if flag and flag != "":
            sealed[slug] = flag
            del manifest["flag"]
            stripped.append(slug)
            if not args.dry_run:
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        else:
            untouched.append(slug)

    if not args.dry_run:
        SECRETS_FILE.write_text(
            json.dumps(sealed, indent=2, sort_keys=True) + "\n"
        )
        os.chmod(SECRETS_FILE, 0o600)

    mode = "(dry run) " if args.dry_run else ""
    print(f"{mode}stripped {len(stripped)} challenge.json files")
    print(f"{mode}{len(sealed)} flags now in {SECRETS_FILE.relative_to(ROOT)}")
    if untouched:
        print(f"({len(untouched)} challenges already had no `flag` field)")


if __name__ == "__main__":
    main()
