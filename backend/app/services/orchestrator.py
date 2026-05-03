"""Compatibility shim for pre-Phase-9 imports.

The real implementation lives in :mod:`app.services.orchestration`.
This module is kept only so any straggler import paths (router
imports, tests, ad-hoc scripts) continue to resolve. Slated for
removal in Phase 12 alongside the rest of the legacy admin surface.
"""

from app.services.orchestration import (  # noqa: F401
    cleanup_expired,
    get_docker_client,
    get_instance_status,
    launch_instance,
    stop_instance,
)

__all__ = [
    "cleanup_expired",
    "get_docker_client",
    "get_instance_status",
    "launch_instance",
    "stop_instance",
]
