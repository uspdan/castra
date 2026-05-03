"""Long-lived Docker client wired through the docker-socket-proxy.

The Phase 4 readyz probe and the Phase 9 launcher both share this
single client. It's lazy-built on first access and closed in the
FastAPI ``lifespan`` shutdown hook. Tests can substitute the client
via ``set_for_test(...)``.
"""

from __future__ import annotations

import threading
from typing import Optional

import docker
import structlog

from app.config import get_settings

logger = structlog.get_logger()


_client: Optional[docker.DockerClient] = None
_lock = threading.Lock()


def get() -> docker.DockerClient:
    """Return the process-wide Docker client (build on first call)."""
    global _client
    if _client is not None:
        return _client
    with _lock:
        if _client is None:
            settings = get_settings()
            _client = docker.DockerClient(
                base_url=settings.DOCKER_HOST,
                timeout=10,
            )
            logger.info(
                "docker.client.connected",
                base_url=settings.DOCKER_HOST,
            )
    return _client


def warmup() -> None:
    """Force-build the client at startup; used by the lifespan hook."""
    get()


def close() -> None:
    """Close the long-lived client and clear the cache (shutdown hook)."""
    global _client
    with _lock:
        if _client is not None:
            try:
                _client.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("docker.client.close_failed", error=str(exc))
            _client = None


def set_for_test(client: Optional[docker.DockerClient]) -> None:
    """Test seam: replace the cached client (None to clear)."""
    global _client
    with _lock:
        _client = client


__all__ = ["close", "get", "set_for_test", "warmup"]
