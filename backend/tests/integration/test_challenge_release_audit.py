"""Integration tests for the slice-9 ``challenge.released`` audit
event + webhook fan-out.

Replaces the slice-5+ legacy env-var notify_release Slack/Teams
broadcast — the same operators who used to pull off
``SLACK_WEBHOOK_URL`` for release pings now subscribe to the
``challenge.released`` event via the v1 webhook surface.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.models import (
    AuditLedger,
    Challenge,
    TeamType,
    UserRole,
    WebhookDelivery,
    WebhookSubscription,
)


pytestmark = pytest.mark.integration


async def _make_unreleased_challenge(db_session, *, slug: str) -> Challenge:
    challenge = Challenge(
        slug=slug,
        title=f"Unreleased {slug}",
        description="awaiting release",
        category="forensics",
        team=TeamType.blue,
        difficulty=2,
        points=200,
        flag_hash="0" * 64,
        hints=[],
        skills=[],
        mitre_techniques=[],
        docker_image="alpine:3.19",
        docker_port=80,
        docker_config={},
        prerequisite_ids=[],
        is_active=True,
        is_released=False,
        released_at=None,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(challenge)
    await db_session.commit()
    await db_session.refresh(challenge)
    return challenge


class TestChallengeReleaseAudit:
    async def test_release_emits_audit_ledger_event(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin)
        chal = await _make_unreleased_challenge(db_session, slug="rel-audit")
        r = await client.post(
            f"/challenges/{chal.slug}/release", headers=auth_headers(admin)
        )
        assert r.status_code == 200, r.text

        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "challenge.released",
                    AuditLedger.actor_id == str(admin.id),
                )
            )
        ).scalars().all()
        assert rows
        payload = rows[-1].payload
        assert payload["challenge_slug"] == "rel-audit"
        assert payload["title"] == "Unreleased rel-audit"
        assert payload["category"] == "forensics"
        assert payload["points"] == 200

    async def test_release_fans_out_to_webhook_subscription(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin, username="rel-admin")
        # Seed an active subscription targeting an unroutable host
        # so the dispatch fails fast (we only care that a delivery
        # row was attempted).
        sub = WebhookSubscription(
            owner_user_id=admin.id,
            name="release-channel",
            target_url="http://127.0.0.1:1/never",
            secret="s" * 64,
            events=["challenge.released"],
            is_active=True,
        )
        db_session.add(sub)
        await db_session.commit()

        chal = await _make_unreleased_challenge(db_session, slug="rel-hook")
        r = await client.post(
            f"/challenges/{chal.slug}/release", headers=auth_headers(admin)
        )
        assert r.status_code == 200, r.text

        rows = (
            await db_session.execute(
                select(WebhookDelivery).where(
                    WebhookDelivery.event_type == "challenge.released"
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].payload["challenge_slug"] == "rel-hook"
        assert rows[0].attempt == 1
        # Outcome non-OK because the receiver is unreachable.
        assert not rows[0].status.startswith("ok_")

    async def test_release_does_not_fan_out_to_unsubscribed_event(
        self, client, user_factory, auth_headers, db_session
    ):
        admin = await user_factory(role=UserRole.admin, username="rel-admin-2")
        # Subscription only listens for flag-pass; release shouldn't fire it.
        sub = WebhookSubscription(
            owner_user_id=admin.id,
            name="other-channel",
            target_url="http://127.0.0.1:1/never",
            secret="s" * 64,
            events=["challenge.flag.submit.pass"],
            is_active=True,
        )
        db_session.add(sub)
        await db_session.commit()

        chal = await _make_unreleased_challenge(db_session, slug="rel-noop")
        r = await client.post(
            f"/challenges/{chal.slug}/release", headers=auth_headers(admin)
        )
        assert r.status_code == 200

        rows = (
            await db_session.execute(select(WebhookDelivery))
        ).scalars().all()
        assert rows == []
