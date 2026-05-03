"""CLI wrapper for the per-instance egress-allowlist renderer.

Usage::

    python -m app.tools.render_egress_allowlist [--target PATH] [--json]

Defaults to writing
``/etc/tinyproxy/egress-allowlist.conf`` (the path tinyproxy reads
inside the egress-proxy container; in operator setups that mount the
shared volume, this is the path the API process writes through).

After a successful write, hot-reload tinyproxy so the new filter
takes effect — typically::

    docker exec siege-egress-proxy kill -HUP 1

(or restart the egress-proxy service). The reload is operator-side;
the CLI exits 0 on a clean write so a wrapper script can chain it.

Exit codes::

    0 — wrote the file successfully (even if empty / no active
        egress-proxied instances).
    2 — operational failure (DB unreachable, target path not
        writable, etc.).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.database import async_session
from app.services.orchestration.egress import RenderResult, render_to_file


_DEFAULT_TARGET = Path("/etc/tinyproxy/egress-allowlist.conf")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="render_egress_allowlist",
        description=(
            "Render the union of every active egress-proxied "
            "instance's allowlist into a tinyproxy filter file."
        ),
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=_DEFAULT_TARGET,
        help=(
            "Path to write the rendered filter to "
            f"(default: {_DEFAULT_TARGET})"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable summary on stdout.",
    )
    return parser


async def _render(target: Path) -> RenderResult:
    async with async_session() as db:
        return await render_to_file(db, target)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = asyncio.run(_render(args.target))
    except Exception as exc:  # noqa: BLE001 — top-level CLI guard
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        json.dump(
            {
                "target": str(args.target),
                "instance_count": result.instance_count,
                "fqdn_count": result.fqdn_count,
                "rule_count": len(result.rules),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        print(
            f"wrote {args.target} "
            f"(instances={result.instance_count}, "
            f"unique_fqdns={result.fqdn_count}, "
            f"rules={len(result.rules)})"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised via CLI
    sys.exit(main())
