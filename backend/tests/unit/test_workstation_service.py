"""Unit tests for ``app.services.workstation``.

Docker client is mocked. Covers:

* Deterministic per-user port computation (``WEB_PORT_BASE + uid``,
  ``SSH_PORT_BASE + uid``).
* Stale-container sweep before fresh launch.
* Idempotent re-launch returns existing descriptor without
  rotating the password.
* ``reap_idle`` honours the uptime cutoff.
* ``attach_to_network`` is a no-op when the workstation isn't
  running.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _started_at(hours_ago: float) -> dict:
    """Synthesise ``container.attrs['State']`` with a StartedAt
    that's ``hours_ago`` hours in the past, formatted the way
    docker reports it.
    """
    when = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_ago)
    return {"State": {"StartedAt": when.isoformat().replace("+00:00", "Z")}}


def _fake_client():
    """Return a MagicMock that mimics the docker client surface
    the workstation service touches.
    """
    client = MagicMock()
    client.containers.get.side_effect = Exception("no such container")
    client.containers.list.return_value = []
    client.volumes.create.return_value = MagicMock()
    client.networks.get.return_value = MagicMock()
    return client


def test_port_constants():
    """Locked: web on 11000+uid, SSH on 11100+uid."""
    from app.services.workstation import WEB_PORT_BASE, SSH_PORT_BASE
    assert WEB_PORT_BASE == 11000
    assert SSH_PORT_BASE == 11100


def test_get_status_no_container():
    from app.services.workstation import get_status

    fake = _fake_client()
    with patch("app.services.workstation.docker_client.get", return_value=fake):
        d = get_status(user_id=42)
    assert d.running is False
    assert d.container == "seige-workstation-42"
    assert d.ssh_host_port is None


def test_launch_skips_when_running():
    """Re-calling launch against a running workstation returns the
    existing descriptor and does NOT rotate the password.
    """
    from app.services.workstation import launch, WorkstationDescriptor

    existing = WorkstationDescriptor(
        user_id=7, container="seige-workstation-7", running=True,
        ssh_host_port=11107, web_host_port=11007, one_shot_password=None,
    )
    with patch("app.services.workstation.get_status", return_value=existing):
        d = launch(user_id=7)
    assert d is existing
    assert d.one_shot_password is None


def test_launch_sweeps_stale_container():
    """A Created/Exited container with the same name is force-removed
    before a fresh container is created.
    """
    from app.services.workstation import launch

    fake = _fake_client()
    fake.containers.get.side_effect = None
    stale = MagicMock()
    stale.name = "seige-workstation-3"
    fake.containers.get.return_value = stale
    new_c = MagicMock()
    new_c.name = "seige-workstation-3"
    new_c.attrs = {"NetworkSettings": {"Ports": {"2222/tcp": [{"HostPort": "11103"}], "7681/tcp": [{"HostPort": "11003"}]}}}
    fake.containers.run.return_value = new_c

    with patch("app.services.workstation.docker_client.get", return_value=fake), \
         patch("app.services.workstation.get_status") as gs:
        # First call inside launch(): stopped/not running.
        from app.services.workstation import WorkstationDescriptor
        gs.return_value = WorkstationDescriptor(
            user_id=3, container="seige-workstation-3", running=False,
            ssh_host_port=None, web_host_port=None,
        )
        d = launch(user_id=3)
    stale.remove.assert_called_once_with(force=True)
    assert d.running is True
    assert d.one_shot_password is not None
    assert len(d.one_shot_password) == 20  # PASSWORD_LEN


def test_launch_assigns_deterministic_ports():
    """Bind args must be 0.0.0.0:<base+uid>:<container-port>."""
    from app.services.workstation import launch, WEB_PORT_BASE, SSH_PORT_BASE

    fake = _fake_client()
    new_c = MagicMock()
    new_c.name = "seige-workstation-9"
    new_c.attrs = {
        "NetworkSettings": {
            "Ports": {
                "2222/tcp": [{"HostPort": str(SSH_PORT_BASE + 9)}],
                "7681/tcp": [{"HostPort": str(WEB_PORT_BASE + 9)}],
            }
        }
    }
    fake.containers.run.return_value = new_c

    with patch("app.services.workstation.docker_client.get", return_value=fake), \
         patch("app.services.workstation.get_status") as gs:
        from app.services.workstation import WorkstationDescriptor
        gs.return_value = WorkstationDescriptor(
            user_id=9, container="seige-workstation-9", running=False,
            ssh_host_port=None, web_host_port=None,
        )
        launch(user_id=9)

    kwargs = fake.containers.run.call_args.kwargs
    ports = kwargs["ports"]
    assert ports["2222/tcp"] == ("0.0.0.0", SSH_PORT_BASE + 9)
    assert ports["7681/tcp"] == ("0.0.0.0", WEB_PORT_BASE + 9)


def test_attach_to_network_noop_when_stopped():
    from app.services.workstation import attach_to_network

    fake = _fake_client()
    not_running = MagicMock()
    not_running.status = "exited"
    not_running.reload = MagicMock()
    fake.containers.get.side_effect = None
    fake.containers.get.return_value = not_running

    with patch("app.services.workstation.docker_client.get", return_value=fake):
        ok = attach_to_network(user_id=1, network_name="some-net")
    assert ok is False
    fake.networks.get.assert_not_called()


def test_attach_to_network_connects_with_alias():
    from app.services.workstation import attach_to_network

    fake = _fake_client()
    running = MagicMock()
    running.status = "running"
    running.reload = MagicMock()
    fake.containers.get.side_effect = None
    fake.containers.get.return_value = running
    net = MagicMock()
    fake.networks.get.return_value = net

    with patch("app.services.workstation.docker_client.get", return_value=fake):
        ok = attach_to_network(user_id=1, network_name="siege-ch-1-foo")
    assert ok is True
    net.connect.assert_called_once_with(running, aliases=["workstation"])


def test_reap_idle_skips_young_containers():
    from app.services.workstation import reap_idle

    young = MagicMock()
    young.attrs = _started_at(hours_ago=1.0)
    young.labels = {"seige.user_id": "1"}

    fake = _fake_client()
    fake.containers.list.return_value = [young]

    with patch("app.services.workstation.docker_client.get", return_value=fake):
        reaped = reap_idle(max_uptime_hours=8)
    assert reaped == []
    young.stop.assert_not_called()


def test_reap_idle_reaps_old_containers():
    from app.services.workstation import reap_idle

    old = MagicMock()
    old.attrs = _started_at(hours_ago=24.0)
    old.labels = {"seige.user_id": "7"}
    old.name = "seige-workstation-7"

    fake = _fake_client()
    fake.containers.list.return_value = [old]

    with patch("app.services.workstation.docker_client.get", return_value=fake):
        reaped = reap_idle(max_uptime_hours=8)
    assert reaped == [7]
    old.stop.assert_called_once()
    old.remove.assert_called_once()
