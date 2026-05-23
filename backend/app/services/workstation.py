"""Per-player analyst-workstation lifecycle.

A workstation is one container per user, named
``seige-workstation-<user_id>``, joined to the ``siege-range``
user-defined network so it can DNS-resolve every challenge
container by name. Its ``/home/analyst`` is backed by a named
volume keyed on the user id so notes/history/scripts survive
restarts.

The workstation image (``siege/workstation:latest``) is built by
``make workstation-build`` once per deploy. This service does
*not* build the image — it only orchestrates per-user instances.

State is intentionally derived from Docker (is the container
running? what host port did Docker assign?) rather than from a DB
table — workstations are ephemeral and there's no benefit to a
schema migration for them. The launch response carries a
**one-shot password** that the player must capture; if they lose
it, they stop + relaunch and a fresh one is generated.
"""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from typing import Optional

import structlog

from app.services.orchestration import docker_client

logger = structlog.get_logger()

# Tunables. Kept here rather than in app.config because the
# workstation surface is opt-in — admins who deploy it can patch
# constants without touching the broader config schema.
WORKSTATION_IMAGE = "siege/workstation:latest"
# Network the workstation joins. ``None`` ⇒ docker's default
# bridge. Per-instance challenge networks are attached on demand
# by the launcher hook (``attach_to_network``).
NETWORK_NAME: Optional[str] = None
SSH_PORT = 2222
WEB_PORT = 7681
PASSWORD_LEN = 20

# Deterministic host port ranges. The orchestrator (DinD) compose
# publishes these to the host so each player has a stable URL.
# Bind formula: web shell on 11000+user_id, SSH on 11100+user_id.
WEB_PORT_BASE = 11000
SSH_PORT_BASE = 11100


def _container_name(user_id: int) -> str:
    return f"seige-workstation-{user_id}"


def _volume_name(user_id: int) -> str:
    return f"seige-workstation-home-{user_id}"


def _new_password() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(PASSWORD_LEN))


@dataclass(frozen=True)
class WorkstationDescriptor:
    """What the player needs to know to use the workstation."""

    user_id: int
    container: str
    running: bool
    ssh_host_port: Optional[int]
    web_host_port: Optional[int]
    # Only set on launch; never re-emitted on subsequent /status calls.
    one_shot_password: Optional[str] = None


def _published_port(container, container_port: int) -> Optional[int]:
    """Resolve the host-side port mapped to a container port."""
    ports = (container.attrs.get("NetworkSettings") or {}).get("Ports") or {}
    bindings = ports.get(f"{container_port}/tcp") or []
    if not bindings:
        return None
    try:
        return int(bindings[0].get("HostPort"))
    except (TypeError, ValueError):
        return None


def get_status(*, user_id: int) -> WorkstationDescriptor:
    client = docker_client.get()
    name = _container_name(user_id)
    try:
        c = client.containers.get(name)
    except Exception:
        return WorkstationDescriptor(
            user_id=user_id, container=name, running=False,
            ssh_host_port=None, web_host_port=None,
        )
    c.reload()
    running = c.status == "running"
    return WorkstationDescriptor(
        user_id=user_id,
        container=name,
        running=running,
        ssh_host_port=_published_port(c, SSH_PORT) if running else None,
        web_host_port=_published_port(c, WEB_PORT) if running else None,
    )


def launch(*, user_id: int) -> WorkstationDescriptor:
    """Boot the player's workstation. Idempotent — if it's already
    running, returns the current descriptor *without* rotating the
    password (the caller already has it from the original launch).
    """
    existing = get_status(user_id=user_id)
    if existing.running:
        logger.info("workstation.launch.already_running", user_id=user_id)
        return existing

    client = docker_client.get()

    # Sweep any stale Created/Exited container with the same name.
    # The previous launch may have died mid-flight (image not yet
    # loaded, network not present, etc.); a name conflict at
    # `containers.run` would mask the real error.
    name = _container_name(user_id)
    try:
        stale = client.containers.get(name)
        stale.remove(force=True)
        logger.info("workstation.launch.swept_stale", user_id=user_id, container=name)
    except Exception:
        pass

    password = _new_password()

    # Make sure the volume exists. `volumes.create` is idempotent
    # when an identically-named volume already exists.
    client.volumes.create(name=_volume_name(user_id))

    run_kwargs = dict(
        image=WORKSTATION_IMAGE,
        name=name,
        detach=True,
        auto_remove=False,
        hostname=f"workstation-{user_id}",
        environment={
            "SIEGE_WORKSTATION_PASSWORD": password,
            "SIEGE_WORKSTATION_HOSTNAME": f"workstation-{user_id}",
        },
        # Deterministic per-user host ports. Inside DinD they bind
        # to 0.0.0.0 so the orchestrator's compose publish-range
        # (11000-11199:11000-11199) can carry them through to the
        # host. Each player has a stable URL —
        # ``http://<host>:11000+user_id/`` — that survives
        # workstation restart.
        ports={
            f"{SSH_PORT}/tcp": ("0.0.0.0", SSH_PORT_BASE + user_id),
            f"{WEB_PORT}/tcp": ("0.0.0.0", WEB_PORT_BASE + user_id),
        },
        volumes={
            _volume_name(user_id): {"bind": "/home/analyst", "mode": "rw"},
        },
        labels={
            "seige.workstation": "1",
            "seige.user_id": str(user_id),
        },
        restart_policy={"Name": "unless-stopped"},
        # R20 audit finding — drop every Linux capability the
        # workstation doesn't need. ttyd binds :7681, sshd binds
        # :2222, chpasswd writes /etc/shadow — these need
        # NET_BIND_SERVICE (ports >1024 don't actually need this on
        # modern Linux, but ttyd is conservative) and CHOWN + DAC*
        # for /home/analyst seeding. Everything else is denied.
        cap_drop=["ALL"],
        cap_add=[
            "CHOWN",
            "DAC_OVERRIDE",
            "FOWNER",
            "SETGID",
            "SETUID",
            "NET_BIND_SERVICE",
            "KILL",
        ],
        security_opt=[
            "no-new-privileges:true",
        ],
    )
    if NETWORK_NAME:
        run_kwargs["network"] = NETWORK_NAME
    container = client.containers.run(**run_kwargs)
    container.reload()
    logger.info(
        "workstation.launch.ok",
        user_id=user_id, container=container.name,
        ssh_port=_published_port(container, SSH_PORT),
        web_port=_published_port(container, WEB_PORT),
    )
    return WorkstationDescriptor(
        user_id=user_id,
        container=container.name,
        running=True,
        ssh_host_port=_published_port(container, SSH_PORT),
        web_host_port=_published_port(container, WEB_PORT),
        one_shot_password=password,
    )


def attach_to_network(*, user_id: int, network_name: str) -> bool:
    """Connect the user's running workstation to a per-instance
    challenge network so it can DNS-resolve the challenge by alias.

    No-op (returns False) if the workstation isn't running. Logs
    and swallows any docker-side failure — workstation attachment
    is a UX nicety, not a correctness requirement, so it should
    never block a challenge launch.
    """
    client = docker_client.get()
    try:
        c = client.containers.get(_container_name(user_id))
    except Exception:
        return False
    c.reload()
    if c.status != "running":
        return False
    try:
        network = client.networks.get(network_name)
        network.connect(c, aliases=["workstation"])
        logger.info(
            "workstation.attach.ok",
            user_id=user_id, network=network_name,
        )
        return True
    except Exception as exc:
        logger.warning(
            "workstation.attach.failed",
            user_id=user_id, network=network_name, error=str(exc),
        )
        return False


def reap_idle(*, max_uptime_hours: int = 8) -> list[int]:
    """Stop every running workstation older than ``max_uptime_hours``.

    Returns the list of user_ids whose workstation was reaped.
    Called from the scheduler on an hourly interval. The home
    volume is preserved — only the container is removed — so an
    idle-reaped player loses no state when they next click Launch.
    """
    import datetime as dt

    client = docker_client.get()
    reaped: list[int] = []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=max_uptime_hours)
    try:
        containers = client.containers.list(
            filters={"label": "seige.workstation=1"}
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("workstation.reap.list_failed", error=str(exc))
        return reaped
    for c in containers:
        try:
            started_at = dt.datetime.fromisoformat(
                c.attrs["State"]["StartedAt"].replace("Z", "+00:00")
            )
        except Exception:  # noqa: BLE001
            continue
        if started_at >= cutoff:
            continue
        try:
            uid = int((c.labels or {}).get("seige.user_id") or "0")
        except ValueError:
            continue
        try:
            c.stop(timeout=10)
            c.remove(force=True)
            reaped.append(uid)
            logger.info(
                "workstation.reap.ok",
                user_id=uid, container=c.name,
                uptime_hours=(dt.datetime.now(dt.timezone.utc) - started_at).total_seconds() / 3600,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("workstation.reap.failed", user_id=uid, error=str(exc))
    return reaped


def stop(*, user_id: int) -> bool:
    """Stop and remove the player's workstation. Volume is preserved."""
    client = docker_client.get()
    try:
        c = client.containers.get(_container_name(user_id))
    except Exception:
        return False
    try:
        c.stop(timeout=10)
    except Exception:
        pass
    try:
        c.remove(force=True)
    except Exception:
        pass
    logger.info("workstation.stop.ok", user_id=user_id)
    return True
