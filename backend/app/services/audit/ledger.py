"""Single-writer hash-chained audit ledger.

Public API:
    await append(db, event_type, actor_type, ..., payload, ...)

Invariants:
    - The ledger is append-only. The DB enforces this via triggers; this
      module enforces it by being the only writer.
    - ``seq`` is monotonic, gap-free, starting at 1.
    - ``this_hash`` over a stable, canonical encoding of the row's
      content (including ``prev_hash``). The first row uses the
      all-zeros ``GENESIS_HASH`` as its predecessor.
    - Concurrent appends are serialised by a Postgres transaction-level
      advisory lock, so two writers cannot race the tail read.

Same-transaction guarantee: ``append`` calls ``db.flush()`` but never
``db.commit()``. The caller's surrounding transaction commits the
ledger row atomically with the business write, or rolls back together
with it.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLedger
from app.services.audit.events import AuditError, validate_event


GENESIS_HASH: str = "0" * 64

# Arbitrary positive int63 constant scoped to this subsystem;
# pg_advisory_xact_lock accepts a signed bigint (int64). Keep stable
# across deploys — changing it would split the lock domain.
_LEDGER_LOCK_KEY: int = 0x5345_4147_4C44_4752  # 'SEAGLDGR' — fits in int64


def _canonicalise(record: dict[str, Any]) -> bytes:
    """Stable JSON encoding for hashing.

    Sorted keys, no insignificant whitespace, ASCII-escape non-ASCII,
    UTF-8 output. Keys present in the dict — including ``None`` values —
    are hashed; missing keys are absent from the canonical form. Callers
    must always pass the same key set, which the schema in this module
    guarantees.
    """

    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def compute_hash(
    *,
    seq: int,
    prev_hash: str,
    event_type: str,
    actor_type: str,
    actor_id: str | None,
    resource_type: str | None,
    resource_id: str | None,
    ip_address: str | None,
    request_id: str | None,
    payload: dict[str, Any],
    created_at: datetime,
) -> str:
    """SHA-256 over the canonical encoding of the row.

    Exposed for the verifier; not for direct use by emit-point callers.
    """

    record = {
        "seq": seq,
        "prev_hash": prev_hash,
        "event_type": event_type,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "ip_address": ip_address,
        "request_id": request_id,
        "payload": payload,
        # ISO 8601, UTC, microsecond precision — matches what we'll
        # observe when re-reading the column.
        "created_at": created_at.astimezone(timezone.utc).isoformat(),
    }
    return hashlib.sha256(_canonicalise(record)).hexdigest()


async def append(
    db: AsyncSession,
    *,
    event_type: str,
    actor_type: str,
    payload: dict[str, Any],
    actor_id: str | int | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> AuditLedger:
    """Append a single row to the ledger inside the caller's transaction.

    Raises:
        AuditError: on unknown event type / actor type / malformed payload.
    """

    validate_event(event_type, actor_type, payload)

    # Normalise non-string ids to strings — the column is a string so the
    # canonical hash sees a stable type.
    actor_id_str = None if actor_id is None else str(actor_id)
    resource_id_str = None if resource_id is None else str(resource_id)

    # Serialise concurrent appends. Released at transaction end (commit
    # or rollback) — no manual unlock needed, no leak on error.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(:k)").bindparams(k=_LEDGER_LOCK_KEY)
    )

    tail = (
        await db.execute(
            select(AuditLedger.seq, AuditLedger.this_hash)
            .order_by(AuditLedger.seq.desc())
            .limit(1)
        )
    ).first()

    if tail is None:
        seq = 1
        prev_hash = GENESIS_HASH
    else:
        seq = int(tail.seq) + 1
        prev_hash = tail.this_hash

    created_at = datetime.now(timezone.utc)
    this_hash = compute_hash(
        seq=seq,
        prev_hash=prev_hash,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id_str,
        resource_type=resource_type,
        resource_id=resource_id_str,
        ip_address=ip_address,
        request_id=request_id,
        payload=payload,
        created_at=created_at,
    )

    row = AuditLedger(
        seq=seq,
        prev_hash=prev_hash,
        this_hash=this_hash,
        event_type=event_type,
        actor_type=actor_type,
        actor_id=actor_id_str,
        resource_type=resource_type,
        resource_id=resource_id_str,
        ip_address=ip_address,
        request_id=request_id,
        payload=payload,
        created_at=created_at,
    )
    db.add(row)
    # Flush so a uniqueness violation surfaces here, not at commit.
    # The caller commits the surrounding transaction.
    try:
        await db.flush()
    except Exception as exc:  # pragma: no cover - surfaced to caller
        raise AuditError(f"failed to append audit ledger row: {exc}") from exc
    return row
