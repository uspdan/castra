"""Per-instance egress proxy sidecar.

The shared ``egress-proxied`` profile multiplexes every active
instance's allowlist through a single ``siege-egress-proxy`` container
(see :mod:`app.services.orchestration.egress`). That works but means
one instance's allowlist is reachable to *every* other instance — the
proxy answers requests by URL pattern, not by source.

The ``egress-proxied-sidecar`` profile spawns a dedicated tinyproxy
container per instance, attached only to that instance's internal
bridge. The challenge's allowlist is the *only* one that sidecar
loads, so cross-instance leakage is eliminated.

This module owns the sidecar lifecycle:

- :func:`render_sidecar_filter`  — render allowlist regex lines
- :func:`launch_sidecar`         — spawn the proxy container
- :func:`teardown_sidecar`       — best-effort stop + remove

The launcher reaches for these when the challenge's profile selects
``egress-proxied-sidecar``; cleanup paths call
:func:`teardown_sidecar` so a removed instance never leaks a sidecar
container.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Iterable, List, Optional

import structlog

from app.services.orchestration.egress import _fqdn_to_regex


logger = structlog.get_logger()


SIDECAR_IMAGE_DEFAULT = "siege-egress-sidecar:latest"
SIDECAR_HOSTNAME = "egress-sidecar"
SIDECAR_LISTEN_PORT = 8888

_SIDECAR_LABEL_KEY = "siege.role"
_SIDECAR_LABEL_VALUE = "egress-sidecar"
_SIDECAR_NAME_PREFIX = "siege-egress-sidecar"


@dataclass(frozen=True)
class SidecarLaunch:
    """Result of a successful sidecar launch."""

    container_id: str
    container_name: str
    listen_url: str  # http://<container_name>:<port>


def render_sidecar_filter(allowlist: Iterable[str]) -> str:
    """Render a per-instance tinyproxy allowlist file.

    Each non-empty entry is normalised + converted to a regex with
    :func:`_fqdn_to_regex`. Duplicates are collapsed; the result is a
    deterministic, sorted set of regex lines plus a generated header.
    Empty allowlist yields a header-only file (deny-all under
    ``FilterDefaultDeny Yes``), which is the safe default.
    """

    seen: set[str] = set()
    rules: List[str] = []
    for entry in allowlist:
        regex = _fqdn_to_regex(entry)
        if not regex or regex in seen:
            continue
        seen.add(regex)
        rules.append(regex)
    rules.sort()

    header = [
        "# Auto-generated per-instance allowlist (sidecar)",
        f"# rule_count: {len(rules)}",
        "#",
        "# tinyproxy FilterDefaultDeny Yes is in effect.",
        "",
    ]
    return "\n".join(header + rules + [""])


def _make_container_name(instance_label: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in instance_label)
    return f"{_SIDECAR_NAME_PREFIX}-{safe[:48]}-{secrets.token_hex(3)}"


def launch_sidecar(
    docker_client_obj,
    *,
    network_name: str,
    allowlist: Iterable[str],
    instance_label: str,
    image: str = SIDECAR_IMAGE_DEFAULT,
) -> SidecarLaunch:
    """Spawn a tinyproxy sidecar attached to ``network_name``.

    The rendered filter is passed via the ``EGRESS_ALLOWLIST`` env var;
    the sidecar entrypoint writes it to the configured filter file
    before tinyproxy starts.

    Caller is responsible for tearing the sidecar down on any
    subsequent failure (the launcher's cleanup branch already covers
    challenge-container errors). On a docker-py error here, the
    exception propagates so the launcher rolls back the per-instance
    network and the caller maps to a 5xx.
    """

    rendered = render_sidecar_filter(allowlist)
    container_name = _make_container_name(instance_label)

    logger.info(
        "sidecar.launch",
        network=network_name,
        rule_count=rendered.count("\n^"),
        container=container_name,
    )

    container = docker_client_obj.containers.run(
        image=image,
        name=container_name,
        hostname=SIDECAR_HOSTNAME,
        detach=True,
        environment={"EGRESS_ALLOWLIST": rendered},
        network=network_name,
        read_only=True,
        tmpfs={"/tmp": "size=8M,noexec,nosuid"},
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        mem_limit="64m",
        pids_limit=64,
        labels={
            _SIDECAR_LABEL_KEY: _SIDECAR_LABEL_VALUE,
            "siege.instance": instance_label,
        },
    )

    return SidecarLaunch(
        container_id=container.id,
        container_name=container_name,
        listen_url=f"http://{container_name}:{SIDECAR_LISTEN_PORT}",
    )


def teardown_sidecar(
    docker_client_obj,
    container_id: Optional[str],
) -> bool:
    """Stop + remove the sidecar container.

    Best-effort: returns ``True`` on a clean stop+remove, ``False`` on
    any failure (container already gone, docker socket flapping). The
    caller never propagates — a stuck sidecar must not block the
    cleanup path.
    """

    if not container_id:
        return False
    try:
        container = docker_client_obj.containers.get(container_id)
        container.stop(timeout=5)
        container.remove(force=True)
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning(
            "sidecar.teardown_failed",
            container_id=container_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        return False


__all__ = [
    "SidecarLaunch",
    "SIDECAR_HOSTNAME",
    "SIDECAR_IMAGE_DEFAULT",
    "SIDECAR_LISTEN_PORT",
    "launch_sidecar",
    "render_sidecar_filter",
    "teardown_sidecar",
]
