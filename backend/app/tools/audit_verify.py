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

from sqlalchemy import select

from app.database import async_session
from app.models import AuditLedger
from app.services.audit.ledger import GENESIS_HASH, compute_hash


async def _verify() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    rows_checked = 0
    last_seq = 0
    last_hash = GENESIS_HASH

    async with async_session() as db:
        result = await db.execute(
            select(AuditLedger).order_by(AuditLedger.seq.asc())
        )
        for row in result.scalars():
            rows_checked += 1
            expected_seq = last_seq + 1
            if row.seq != expected_seq:
                findings.append(
                    {
                        "kind": "seq_gap",
                        "expected_seq": expected_seq,
                        "found_seq": int(row.seq),
                        "row_id": int(row.id),
                    }
                )
            if row.prev_hash != last_hash:
                findings.append(
                    {
                        "kind": "prev_hash_mismatch",
                        "seq": int(row.seq),
                        "expected_prev_hash": last_hash,
                        "found_prev_hash": row.prev_hash,
                        "row_id": int(row.id),
                    }
                )
            recomputed = compute_hash(
                seq=int(row.seq),
                prev_hash=row.prev_hash,
                event_type=row.event_type,
                actor_type=row.actor_type,
                actor_id=row.actor_id,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                ip_address=row.ip_address,
                request_id=row.request_id,
                payload=row.payload,
                created_at=row.created_at,
            )
            if recomputed != row.this_hash:
                findings.append(
                    {
                        "kind": "hash_mismatch",
                        "seq": int(row.seq),
                        "stored_hash": row.this_hash,
                        "recomputed_hash": recomputed,
                        "row_id": int(row.id),
                    }
                )
            last_seq = int(row.seq)
            last_hash = row.this_hash

    return {
        "ok": not findings,
        "rows_checked": rows_checked,
        "tail_seq": last_seq,
        "tail_hash": last_hash,
        "findings": findings,
    }


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
