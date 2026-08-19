"""Re-walk the audit ledger and verify the hash chain.

Usage:
    python -m app.tools.audit_verify           # exit 0 on intact chain
    python -m app.tools.audit_verify --json    # machine-readable report

Exit codes:
    0  chain intact (or empty)
    1  tamper detected (gap, wrong prev_hash, hash mismatch)
    2  operational failure (DB unreachable, etc.)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any


from app.database import async_session


async def _verify() -> dict[str, Any]:
    # Thin session-owning wrapper. The walk itself lives in
    # ``app.services.audit.ledger.verify_chain`` so callers with their
    # own transaction (the drill evidence report) can verify inside it.
    from app.services.audit.ledger import verify_chain

    async with async_session() as db:
        return await verify_chain(db)


async def _amain(json_out: bool) -> int:
    try:
        report = await _verify()
    except Exception as exc:  # noqa: BLE001 — final boundary, structured stderr.
        sys.stderr.write(
            json.dumps({"ok": False, "error": "operational", "detail": str(exc)})
            + "\n"
        )
        return 2

    if json_out:
        sys.stdout.write(json.dumps(report) + "\n")
    else:
        if report["ok"]:
            sys.stdout.write(
                f"audit-ledger OK — {report['rows_checked']} rows, "
                f"tail seq={report['tail_seq']}\n"
            )
        else:
            sys.stdout.write(
                f"audit-ledger TAMPER — {len(report['findings'])} finding(s) "
                f"in {report['rows_checked']} row(s)\n"
            )
            for f in report["findings"]:
                sys.stdout.write(f"  - {f}\n")
    return 0 if report["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the audit ledger hash chain.")
    parser.add_argument(
        "--json", action="store_true", help="emit a JSON report on stdout"
    )
    args = parser.parse_args()
    return asyncio.run(_amain(args.json))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
