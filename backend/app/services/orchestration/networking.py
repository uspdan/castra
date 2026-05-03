"""Per-instance network plumbing.

For ``bridge-isolated`` profiles the launcher creates a dedicated
docker bridge per instance and attaches only the challenge container.
For ``egress-proxied`` the bridge is created with ``internal=true``
and the egress-proxy container is attached so the challenge can only
reach the outside world via the proxy.

The egress-proxy container is created out-of-band by docker-compose
under the name ``EGRESS_PROXY_CONTAINER`` (defaults to
``siege-egress-proxy``). It must already be running when an
``egress-proxied`` instance launches; we attach it to the new bridge
without restarting it.
"""

from __future__ import annotations

import secrets
from typing import Final

import docker
import structlog

logger = structlog.get_logger()


EGRESS_PROXY_CONTAINER: Final = "siege-egress-proxy"


def _name(user_id: int, slug: str) -> str:
    return f"siege-ch-{user_id}-{slug}-{secrets.token_hex(4)}"


def create_instance_network(
    client: docker.DockerClient,
    *,
    user_id: int,
    slug: str,
    egress_proxied: bool,
    internal_only: bool = False,
):
    """Create a dedicated bridge for one instance.

    ``egress_proxied`` (mutually exclusive with ``internal_only``):
    creates an internal=true bridge and attaches the shared
    ``siege-egress-proxy`` container.

    ``internal_only``: creates an internal=true bridge with **no**
    upstream proxy attached. Caller is expected to attach a
    per-instance sidecar (the ``egress-proxied-sidecar`` profile);
    leaving the bridge sidecar-less means the challenge has no
    outbound network at all.

    Returns the docker-py ``Network`` object. Caller is responsible for
    removing it on tear-down.
    """
    if egress_proxied and internal_only:
        raise ValueError(
            "egress_proxied and internal_only are mutually exclusive"
        )

    name = _name(user_id, slug)
    if egress_proxied:
        network = client.networks.create(
            name,
            driver="bridge",
            internal=True,
            labels={"siege.network": "egress-proxied"},
        )
        _attach_egress_proxy(client, network)
    elif internal_only:
        network = client.networks.create(
            name,
            driver="bridge",
            internal=True,
            labels={"siege.network": "egress-proxied-sidecar"},
        )
    else:
        network = client.networks.create(
            name,
            driver="bridge",
            internal=False,
            labels={"siege.network": "bridge-isolated"},
        )
    return network


def _attach_egress_proxy(client: docker.DockerClient, network) -> None:
    """Connect the running egress-proxy container to ``network``.

    Raises ``EgressProxyUnavailable`` if the proxy isn't running.
    """
    try:
        proxy = client.containers.get(EGRESS_PROXY_CONTAINER)
    except docker.errors.NotFound as exc:
        raise EgressProxyUnavailable(
            f"egress proxy container {EGRESS_PROXY_CONTAINER!r} not running"
        ) from exc
    network.connect(proxy)
    logger.info(
        "egress_proxy.attached",
        network=network.name,
        proxy=EGRESS_PROXY_CONTAINER,
    )


def remove_network(client: docker.DockerClient, network_name: str) -> None:
    """Best-effort tear-down of an instance bridge."""
    try:
        network = client.networks.get(network_name)
    except docker.errors.NotFound:
        return
    try:
        network.remove()
    except docker.errors.APIError as exc:
        logger.warning("network.remove_failed", network=network_name, error=str(exc))


class EgressProxyUnavailable(RuntimeError):
    """The egress proxy isn't running; the egress-proxied profile can't launch."""


__all__ = [
    "EGRESS_PROXY_CONTAINER",
    "EgressProxyUnavailable",
    "create_instance_network",
    "remove_network",
]
