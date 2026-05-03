"""Smoke test for the integration-test scaffolding.

Asserts that:
    - testcontainer Postgres is reachable through the rebuilt engine,
    - alembic upgrade head has run (audit_ledger table + immutability
      trigger from migration 002 are in place),
    - per-test savepoint isolation actually rolls back changes between
      tests,
    - the FastAPI client is wired up against the test session.

If any of these fail, the rest of the integration suite is unreliable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.integration


async def test_engine_points_at_testcontainer(db_session):
    # Sanity: the engine the session is bound to should NOT be the dev
    # default (db:5432). It should be whatever testcontainer assigned.
    url = str(db_session.bind.engine.url)
    assert "@db:" not in url, f"engine still points at the dev DB: {url}"
    assert "asyncpg" in url


async def test_alembic_ran_audit_ledger_table_exists(db_session):
    result = await db_session.execute(
        text(
            "SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_ledger'"
        )
    )
    assert result.scalar() == 1


async def test_audit_ledger_immutability_trigger_installed(db_session):
    # Migration 002 installs BEFORE UPDATE / BEFORE DELETE triggers. If
    # alembic ran, the trigger names exist in pg_trigger.
    result = await db_session.execute(
        text(
            "SELECT count(*) FROM pg_trigger "
            "WHERE tgname IN ('audit_ledger_no_update', 'audit_ledger_no_delete')"
        )
    )
    assert result.scalar() == 2


async def test_savepoint_rollback_isolates_tests_part_a(db_session, user_factory):
    # Insert a row; the next test must not see it.
    await user_factory(username="iso-canary-A", email="canary-a@test.local")


async def test_savepoint_rollback_isolates_tests_part_b(db_session):
    from sqlalchemy import select
    from app.models import User

    result = await db_session.execute(
        select(User).where(User.username == "iso-canary-A")
    )
    assert result.scalar_one_or_none() is None, (
        "row from previous test leaked across the savepoint boundary — "
        "isolation is broken"
    )


async def test_health_endpoint_via_client(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "2.4.1"}
