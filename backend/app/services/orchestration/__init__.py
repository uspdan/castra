"""Container orchestration package (Phase 9).

Public surface preserved for the routers/scheduler/health-probe that
imported the pre-Phase-9 ``app.services.orchestrator`` module. New
callers should import from the submodules directly.
"""

from app.services.orchestration import docker_client, networking, profiles
from app.services.orchestration.cleanup import (
    cleanup_expired,
    get_instance_status,
    stop_instance,
)
from app.services.orchestration.forbidden import (
    ForbiddenContainerOption,
    enforce_no_forbidden,
)
from app.services.orchestration.launcher import (
    MissingImageDigest,
    PostPullDigestMismatch,
    launch_instance,
)
from app.services.orchestration.profiles import (
    PROFILES,
    ContainerProfile,
    UnknownProfile,
)


def get_docker_client():
    """Backwards-compatible shim returning the long-lived client."""
    return docker_client.get()


__all__ = [
    "ContainerProfile",
    "ForbiddenContainerOption",
    "MissingImageDigest",
    "PostPullDigestMismatch",
    "PROFILES",
    "UnknownProfile",
    "cleanup_expired",
    "docker_client",
    "enforce_no_forbidden",
    "get_docker_client",
    "get_instance_status",
    "launch_instance",
    "networking",
    "profiles",
    "stop_instance",
]
