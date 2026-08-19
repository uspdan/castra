"""Drill evidence reports (services/drill_report + the admin route).

The claim under test: the pack is evidence, not a summary. That means
timeline entries carry real ledger seq/hash values, the fingerprint is
recomputable from the canonical JSON, and generating a report leaves
its own ledger trail.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models import AuditLedger, UserRole


@pytest.fixture
async def drill_window(db_session, user_factory, challenge_factory):
    """A player, a challenge, and one pass + one fail in the ledger."""

    from app.services.audit import EventType, append

    player = await user_factory(username="drill-player")
    chal = await challenge_factory(slug="drill-chal", points=100)

    for event, extra in (
        (EventType.FLAG_SUBMIT_FAIL, {}),
        (
            EventType.FLAG_SUBMIT_PASS,
            {"points_awarded": 100, "is_first_blood": True},
        ),
    ):
        await append(
            db_session,
            event_type=event,
            actor_type="user",
            actor_id=str(player.id),
            payload={"challenge_slug": chal.slug, **extra},
        )
    await db_session.commit()

    now = datetime.now(timezone.utc)
    return {
        "player": player,
        "challenge": chal,
        "since": (now - timedelta(hours=1)).isoformat(),
        "until": (now + timedelta(hours=1)).isoformat(),
    }


class TestDrillReportRoute:
    async def test_requires_admin(self, client, drill_window, user_factory, auth_headers):
        user = await user_factory()
        r = await client.get(
            "/admin/reports/drill",
            params={"since": drill_window["since"], "until": drill_window["until"]},
            headers=auth_headers(user),
        )
        assert r.status_code == 403

    async def test_needs_a_window_or_competition(
        self, client, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.get("/admin/reports/drill", headers=auth_headers(admin))
        assert r.status_code == 422

    async def test_pack_contents(
        self, client, drill_window, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.get(
            "/admin/reports/drill",
            params={"since": drill_window["since"], "until": drill_window["until"]},
            headers=auth_headers(admin),
        )
        assert r.status_code == 200
        pack = r.json()

        assert pack["report_type"] == "castra.drill_evidence.v1"
        assert pack["summary"]["submissions_pass"] == 1
        assert pack["summary"]["submissions_fail"] == 1
        assert [p["username"] for p in pack["participants"]] == ["drill-player"]
        assert [e["slug"] for e in pack["exercises"]] == ["drill-chal"]

        # Timeline entries are ledger-grade: real seq + 64-hex hashes.
        assert len(pack["timeline"]) == 2
        for entry in pack["timeline"]:
            assert entry["seq"] > 0
            assert len(entry["hash"]) == 64

        assert pack["integrity"]["chain_intact"] is True
        assert pack["integrity"]["rows_checked"] >= 2

    async def test_fingerprint_is_recomputable(
        self, client, drill_window, user_factory, auth_headers
    ):
        # The attestation must be verifiable by an auditor holding only
        # the JSON: sha256 over the canonical body minus the
        # attestation block itself.
        from castra_spec import canonical_json

        admin = await user_factory(role=UserRole.admin)
        r = await client.get(
            "/admin/reports/drill",
            params={"since": drill_window["since"], "until": drill_window["until"]},
            headers=auth_headers(admin),
        )
        pack = r.json()
        claimed = pack.pop("attestation")["fingerprint"]
        recomputed = hashlib.sha256(canonical_json(pack)).hexdigest()
        assert recomputed == claimed

    async def test_generation_is_itself_ledgered(
        self, client, drill_window, db_session, user_factory, auth_headers
    ):
        admin = await user_factory(role=UserRole.admin)
        r = await client.get(
            "/admin/reports/drill",
            params={"since": drill_window["since"], "until": drill_window["until"]},
            headers=auth_headers(admin),
        )
        fingerprint = r.json()["attestation"]["fingerprint"]

        row = (
            await db_session.execute(
                select(AuditLedger)
                .where(AuditLedger.event_type == "report.drill.generated")
                .order_by(AuditLedger.seq.desc())
                .limit(1)
            )
        ).scalars().first()
        assert row is not None
        assert row.actor_id == str(admin.id)
        assert row.payload["fingerprint"] == fingerprint

    async def test_pdf_renders_with_escaping(
        self, client, db_session, user_factory, challenge_factory, auth_headers
    ):
        # The template env now autoescapes; a hostile display_name must
        # not survive into the rendered HTML as markup. Render the
        # template directly rather than driving weasyprint — the PDF
        # step adds minutes and tests nothing about escaping.
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        from pathlib import Path
        import app.routers.admin as admin_mod

        template_dir = Path(admin_mod.__file__).parent.parent / "templates"
        env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html"]),
        )
        template = env.get_template("reports/drill_report.html")
        html = template.render(report={
            "generated_at": "t", "generated_by": "a",
            "window": {"since": "s", "until": "u"},
            "competition": None,
            "summary": {"participants": 1, "exercises": 0, "solves": 0,
                        "submissions_pass": 0, "submissions_fail": 0,
                        "mitre_techniques_exercised": []},
            "integrity": {"chain_verified_at": "t", "rows_checked": 0,
                          "findings": [], "chain_intact": True,
                          "chain_head_seq": 0, "chain_head_hash": "0" * 64},
            "participants": [{
                "username": "u",
                "display_name": "<script>alert(1)</script>",
                "team": "red",
            }],
            "exercises": [], "timeline": [],
            "attestation": {"algorithm": "x", "fingerprint": "0" * 64},
        })
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html
