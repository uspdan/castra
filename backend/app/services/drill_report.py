"""Drill evidence reports.

Teams increasingly need to *prove* they exercise — tabletop and
technical-drill evidence turns up in ISO 27001 control reviews, SOC 2
audits, DORA/NIS2 resilience-testing obligations, and cyber-insurance
questionnaires. A scoreboard screenshot is not evidence. This module
builds an evidence pack that is:

* **Grounded in the hash-chained audit ledger.** Every timeline entry
  carries its ledger ``seq`` and ``this_hash``, so an auditor can
  re-derive the chain and confirm no event was inserted or removed
  after the fact.
* **Integrity-attested.** The pack embeds the result of a full chain
  verification run at generation time, plus the chain head, plus a
  sha256 fingerprint of the pack's own canonical JSON.
* **Itself evidenced.** Generating a report appends a
  ``report.drill.generated`` ledger event carrying the fingerprint —
  the evidence trail records that evidence was produced, by whom,
  and with what hash.

The JSON pack is the artefact of record; the PDF rendering in
``routers/admin.py`` is a human-readable view of the same data.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from castra_spec import canonical_json

from app.models import AuditLedger, Challenge, Competition, Solve, User

# Ledger events that constitute drill activity. Auth noise and
# webhook traffic are deliberately excluded — an evidence pack should
# show the exercise, not the plumbing.
_DRILL_EVENT_TYPES = (
    "challenge.flag.submit.pass",
    "challenge.flag.submit.fail",
    "challenge.released",
    "instance.launch",
    "instance.stop",
    "instance.reset",
    "instance.expired",
)


async def build_drill_report(
    db: AsyncSession,
    *,
    since: datetime,
    until: datetime,
    competition: Optional[Competition] = None,
    generated_by: str,
) -> dict[str, Any]:
    """Assemble the evidence pack for a time window.

    Returns the full pack including the ``attestation`` block. The
    caller is responsible for appending the ledger event (it owns the
    session/transaction) — see ``routers/admin.py``.
    """

    # ── Timeline: ledger rows in-window, evidence-grade ────────────
    rows = (
        await db.execute(
            select(AuditLedger)
            .where(
                AuditLedger.created_at >= since,
                AuditLedger.created_at <= until,
                AuditLedger.event_type.in_(_DRILL_EVENT_TYPES),
            )
            .order_by(AuditLedger.seq.asc())
        )
    ).scalars().all()

    timeline = [
        {
            "seq": int(r.seq),
            "hash": r.this_hash,
            "at": r.created_at.isoformat(),
            "event": r.event_type,
            "actor_type": r.actor_type,
            "actor_id": r.actor_id,
            "payload": r.payload,
        }
        for r in rows
    ]

    # ── Participants: everyone who acted in the window ─────────────
    actor_ids = sorted(
        {r.actor_id for r in rows if r.actor_type == "user" and r.actor_id}
    )
    users: list[User] = []
    if actor_ids:
        numeric = [int(a) for a in actor_ids if a.isdigit()]
        users = list(
            (await db.execute(select(User).where(User.id.in_(numeric)))).scalars()
        )
    participants = [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "team": u.team.value if hasattr(u.team, "value") else u.team,
        }
        for u in sorted(users, key=lambda u: u.username)
    ]

    # ── Exercises: challenges touched in-window ────────────────────
    slugs = sorted(
        {
            r.payload.get("challenge_slug")
            for r in rows
            if isinstance(r.payload, dict) and r.payload.get("challenge_slug")
        }
    )
    challenges: list[Challenge] = []
    if slugs:
        challenges = list(
            (await db.execute(select(Challenge).where(Challenge.slug.in_(slugs)))).scalars()
        )
    exercises = [
        {
            "slug": c.slug,
            "title": c.title,
            "category": c.category,
            "difficulty": c.difficulty,
            "team": c.team.value if hasattr(c.team, "value") else c.team,
            "mitre_techniques": list(c.mitre_techniques or []),
        }
        for c in sorted(challenges, key=lambda c: c.slug)
    ]

    # ── Outcomes ───────────────────────────────────────────────────
    solves = (
        await db.execute(
            select(Solve).where(
                Solve.solved_at >= since, Solve.solved_at <= until
            )
        )
    ).scalars().all()
    passes = sum(1 for r in rows if r.event_type == "challenge.flag.submit.pass")
    fails = sum(1 for r in rows if r.event_type == "challenge.flag.submit.fail")
    techniques = sorted(
        {t for e in exercises for t in list(e["mitre_techniques"])}
    )

    summary = {
        "participants": len(participants),
        "exercises": len(exercises),
        "solves": len(solves),
        "submissions_pass": passes,
        "submissions_fail": fails,
        "mitre_techniques_exercised": techniques,
    }

    # ── Integrity: verify the whole chain, right now ───────────────
    from app.services.audit.ledger import verify_chain

    # Caller's session on purpose: the verification must see the same
    # transactional snapshot as the timeline above, or a report
    # generated mid-transaction could attest a chain it isn't showing.
    verification = await verify_chain(db)
    head = (
        await db.execute(
            select(AuditLedger).order_by(AuditLedger.seq.desc()).limit(1)
        )
    ).scalars().first()

    integrity = {
        "chain_verified_at": datetime.now(timezone.utc).isoformat(),
        "rows_checked": verification.get("rows_checked", 0),
        "findings": verification.get("findings", []),
        "chain_intact": not verification.get("findings"),
        "chain_head_seq": int(head.seq) if head else 0,
        "chain_head_hash": head.this_hash if head else None,
    }

    body: dict[str, Any] = {
        "report_type": "castra.drill_evidence.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": generated_by,
        "window": {"since": since.isoformat(), "until": until.isoformat()},
        "competition": (
            {
                "id": competition.id,
                "title": competition.title,
                "starts_at": competition.starts_at.isoformat(),
                "ends_at": competition.ends_at.isoformat(),
            }
            if competition
            else None
        ),
        "summary": summary,
        "participants": participants,
        "exercises": exercises,
        "timeline": timeline,
        "integrity": integrity,
    }

    # Fingerprint over the canonical form of everything above. An
    # auditor holding the JSON can recompute this with one line; the
    # matching ledger event pins when it was produced and by whom.
    fingerprint = hashlib.sha256(canonical_json(body)).hexdigest()
    body["attestation"] = {
        "algorithm": "sha256(canonical_json(body sans attestation))",
        "fingerprint": fingerprint,
    }
    return body
