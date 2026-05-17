"""Integration tests for ``/api/v1/workstation/{status,launch,stop}``.

Mocks the docker client so the tests run in-process without
needing a real docker daemon. Verifies:

* 401 / 403 paths.
* Locked DTO shape (extra='forbid').
* ``ssh_command`` + ``web_url`` derive from request headers
  (X-Forwarded-Host / X-Forwarded-Proto) — important for
  reverse-proxy correctness.
* ``one_shot_password`` is present on launch, absent on status.
* Audit-ledger rows for ``workstation.launch`` and
  ``workstation.stop`` land.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.integration


def _make_descriptor(running: bool, *, with_pw: bool = False) -> Any:
    """Return a ``WorkstationDescriptor`` stand-in."""
    from app.services.workstation import WorkstationDescriptor

    return WorkstationDescriptor(
        user_id=1,
        container="seige-workstation-1",
        running=running,
        ssh_host_port=11101 if running else None,
        web_host_port=11001 if running else None,
        one_shot_password="TEST_PW_xxxxxxx_PW" if (running and with_pw) else None,
    )


@pytest.mark.asyncio
async def test_status_requires_auth(client):
    r = await client.get("/api/v1/workstation/status")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_status_stopped(client, user_factory, auth_headers):
    user = await user_factory(username="ws-status-stopped")
    headers = auth_headers(user)
    with patch("app.services.workstation.get_status", return_value=_make_descriptor(False)):
        r = await client.get("/api/v1/workstation/status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body == {
        "running": False,
        "container": "seige-workstation-1",
        "ssh_host_port": None,
        "web_host_port": None,
        "ssh_command": None,
        "web_url": None,
    }


@pytest.mark.asyncio
async def test_status_running_direct_port(client, user_factory, auth_headers):
    """No X-Forwarded-* → direct port-form URL."""
    user = await user_factory(username="ws-direct")
    headers = auth_headers(user)
    with patch("app.services.workstation.get_status", return_value=_make_descriptor(True)):
        r = await client.get("/api/v1/workstation/status", headers=headers)
    body = r.json()
    assert body["running"] is True
    assert body["ssh_host_port"] == 11101
    assert body["web_host_port"] == 11001
    assert body["ssh_command"] == "ssh -p 11101 analyst@testserver"
    # Direct port URL when un-proxied.
    assert body["web_url"] == "http://testserver:11001/"


@pytest.mark.asyncio
async def test_status_running_proxied_url(client, user_factory, auth_headers):
    """X-Forwarded-Proto + X-Forwarded-Host → path-form proxy URL with
    3-digit zero-padded user id."""
    user = await user_factory(username="ws-proxied")
    headers = {
        **auth_headers(user),
        "X-Forwarded-Host": "range.example.com",
        "X-Forwarded-Proto": "https",
    }
    with patch("app.services.workstation.get_status", return_value=_make_descriptor(True)):
        r = await client.get("/api/v1/workstation/status", headers=headers)
    body = r.json()
    assert body["ssh_command"] == "ssh -p 11101 analyst@range.example.com"
    # 3-digit padding so nginx's regex ``\d{3}`` matches it.
    expected = f"https://range.example.com/workstation/{user.id:03d}/"
    assert body["web_url"] == expected


@pytest.mark.asyncio
async def test_launch_returns_one_shot_password(client, user_factory, auth_headers):
    user = await user_factory(username="ws-launch")
    headers = auth_headers(user)
    desc = _make_descriptor(True, with_pw=True)
    with patch("app.services.workstation.launch", return_value=desc):
        r = await client.post("/api/v1/workstation/launch", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is True
    assert body["one_shot_password"] == "TEST_PW_xxxxxxx_PW"


@pytest.mark.asyncio
async def test_launch_503_when_image_missing(client, user_factory, auth_headers):
    """If the workstation image isn't built the launch service raises;
    the router maps that to 503 unavailable."""
    user = await user_factory(username="ws-no-image")
    headers = auth_headers(user)
    with patch(
        "app.services.workstation.launch",
        side_effect=Exception("no such image: siege/workstation:latest"),
    ):
        r = await client.post("/api/v1/workstation/launch", headers=headers)
    assert r.status_code == 503
    assert "workstation unavailable" in r.json()["detail"]


@pytest.mark.asyncio
async def test_launch_writes_audit_row(client, user_factory, auth_headers, db_session):
    """``workstation.launch`` lands in the hash-chained ledger when a
    fresh container is created (one_shot_password is set)."""
    from app.models import AuditLedger
    from sqlalchemy import select

    user = await user_factory(username="ws-audit")
    headers = auth_headers(user)
    desc = _make_descriptor(True, with_pw=True)
    with patch("app.services.workstation.launch", return_value=desc):
        r = await client.post("/api/v1/workstation/launch", headers=headers)
    assert r.status_code == 200

    rows = (
        await db_session.execute(
            select(AuditLedger).where(AuditLedger.event_type == "workstation.launch")
        )
    ).scalars().all()
    assert len(rows) >= 1
    row = rows[-1]
    assert row.actor_type == "user"
    assert row.actor_id == str(user.id)
    assert row.resource_type == "workstation"
    payload = row.payload
    assert payload["container"] == "seige-workstation-1"
    assert payload["ssh_host_port"] == 11101


@pytest.mark.asyncio
async def test_launch_idempotent_no_audit_on_already_running(
    client, user_factory, auth_headers, db_session
):
    """Re-calling launch against a running workstation returns the
    descriptor with ``one_shot_password=None`` and does NOT append a
    second audit row."""
    from app.models import AuditLedger
    from sqlalchemy import select

    user = await user_factory(username="ws-idem")
    headers = auth_headers(user)
    desc = _make_descriptor(True, with_pw=False)  # already-running case
    with patch("app.services.workstation.launch", return_value=desc):
        r = await client.post("/api/v1/workstation/launch", headers=headers)
    assert r.status_code == 200
    assert r.json()["one_shot_password"] is None
    rows = (
        await db_session.execute(
            select(AuditLedger).where(AuditLedger.event_type == "workstation.launch")
        )
    ).scalars().all()
    # No new audit row for this user.
    assert not any(row.actor_id == str(user.id) for row in rows)


@pytest.mark.asyncio
async def test_stop_writes_audit_row(client, user_factory, auth_headers, db_session):
    from app.models import AuditLedger
    from sqlalchemy import select

    user = await user_factory(username="ws-stop-audit")
    headers = auth_headers(user)
    with patch("app.services.workstation.stop", return_value=True), \
         patch(
             "app.services.workstation.get_status",
             return_value=_make_descriptor(False),
         ):
        r = await client.post("/api/v1/workstation/stop", headers=headers)
    assert r.status_code == 200
    rows = (
        await db_session.execute(
            select(AuditLedger).where(
                AuditLedger.event_type == "workstation.stop",
                AuditLedger.actor_id == str(user.id),
            )
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_stop_no_audit_if_nothing_was_running(
    client, user_factory, auth_headers, db_session
):
    """If the workstation wasn't running, stop() returns False and we
    skip the audit emit."""
    from app.models import AuditLedger
    from sqlalchemy import select

    user = await user_factory(username="ws-stop-noop")
    headers = auth_headers(user)
    with patch("app.services.workstation.stop", return_value=False), \
         patch(
             "app.services.workstation.get_status",
             return_value=_make_descriptor(False),
         ):
        r = await client.post("/api/v1/workstation/stop", headers=headers)
    assert r.status_code == 200
    rows = (
        await db_session.execute(
            select(AuditLedger).where(
                AuditLedger.event_type == "workstation.stop",
                AuditLedger.actor_id == str(user.id),
            )
        )
    ).scalars().all()
    assert len(rows) == 0
