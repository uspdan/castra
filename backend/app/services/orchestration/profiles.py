"""Container-launch profile registry.

A *profile* fully determines the security envelope of a launched
challenge container. Profiles are constants in code, not
runtime-configurable: an operator wanting a new profile lands a code
change with the surrounding ADR. Manifests select a profile by name;
the launcher applies the profile's settings, overriding anything the
manifest tried to set on a profile-managed field.

Adding a profile:
    1. Add an entry to ``PROFILES`` here.
    2. Drop a matching seccomp JSON in ``app/security/seccomp/``.
    3. Update ``docs/security-model.md``.
    4. Update the loader's allow-list (it reads ``PROFILES`` directly,
       so this is automatic).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Mapping, Tuple


class UnknownProfile(LookupError):
    """Raised when a manifest references an unknown profile name."""


@dataclass(frozen=True, slots=True)
class ContainerProfile:
    """Frozen launch envelope.

    All fields are intentionally final; the launcher composes docker-py
    kwargs purely from these values. Manifests cannot override any
    field listed here.
    """

    name: str
    seccomp_profile: str  # short name; resolved via app.security.seccomp
    mem_limit: str  # docker-py format, e.g. "512m"
    cpu_quota: int
    cpu_period: int
    pids_limit: int
    tmpfs: Mapping[str, str]
    ttl_seconds_max: int  # hard ceiling; user-requested TTL clamped
    network_mode: str  # "bridge-isolated" | "egress-proxied"
    egress_allowlist_required: bool
    cap_drop: Tuple[str, ...]
    cap_add: Tuple[str, ...]
    security_opt: Tuple[str, ...] = field(default_factory=tuple)
    read_only: bool = True


_DEFAULT_TMPFS: Final[Mapping[str, str]] = {
    "/tmp": "size=64M,noexec,nosuid",
    "/var/log": "size=32M,noexec,nosuid",
}


_DEFAULT_STRICT = ContainerProfile(
    name="default-strict",
    seccomp_profile="default-strict",
    mem_limit="512m",
    cpu_quota=100_000,
    cpu_period=100_000,
    pids_limit=256,
    tmpfs=_DEFAULT_TMPFS,
    ttl_seconds_max=7_200,
    network_mode="bridge-isolated",
    egress_allowlist_required=False,
    cap_drop=("ALL",),
    cap_add=(),
    security_opt=("no-new-privileges:true",),
    read_only=True,
)


_MALWARE_SANDBOX = ContainerProfile(
    name="malware-sandbox",
    seccomp_profile="malware-sandbox",
    mem_limit="384m",
    cpu_quota=50_000,
    cpu_period=100_000,
    pids_limit=128,
    tmpfs={
        "/tmp": "size=32M,noexec,nosuid",
        "/var/log": "size=16M,noexec,nosuid",
    },
    ttl_seconds_max=1_800,
    network_mode="bridge-isolated",
    egress_allowlist_required=False,
    cap_drop=("ALL",),
    cap_add=(),
    security_opt=("no-new-privileges:true",),
    read_only=True,
)


_EGRESS_PROXIED = ContainerProfile(
    name="egress-proxied",
    seccomp_profile="default-strict",
    mem_limit="512m",
    cpu_quota=100_000,
    cpu_period=100_000,
    pids_limit=256,
    tmpfs=_DEFAULT_TMPFS,
    ttl_seconds_max=3_600,
    network_mode="egress-proxied",
    egress_allowlist_required=True,
    cap_drop=("ALL",),
    cap_add=(),
    security_opt=("no-new-privileges:true",),
    read_only=True,
)


# Per-instance sidecar variant. Functionally identical to
# ``egress-proxied`` for the challenge container, but the launcher
# spawns a dedicated tinyproxy alongside it and routes egress through
# *that* proxy instead of the shared ``siege-egress-proxy``. Each
# sidecar loads only its own challenge's allowlist, so cross-instance
# leakage is structurally impossible.
_EGRESS_PROXIED_SIDECAR = ContainerProfile(
    name="egress-proxied-sidecar",
    seccomp_profile="default-strict",
    mem_limit="512m",
    cpu_quota=100_000,
    cpu_period=100_000,
    pids_limit=256,
    tmpfs=_DEFAULT_TMPFS,
    ttl_seconds_max=3_600,
    network_mode="egress-proxied-sidecar",
    egress_allowlist_required=True,
    cap_drop=("ALL",),
    cap_add=(),
    security_opt=("no-new-privileges:true",),
    read_only=True,
)


# Sprint 9 Phase C — AI/LLM honeypot challenges. Functionally a thin
# variant of ``egress-proxied``: the challenge container can reach the
# inference endpoint via the egress allowlist (operator-supplied
# OpenAI-compatible URL) and nothing else. ttl is shorter (LLM
# challenges should be quick), cap_drop / read_only stay maximal.
_LLM_SANDBOX = ContainerProfile(
    name="llm-sandbox",
    seccomp_profile="default-strict",
    mem_limit="512m",
    cpu_quota=100_000,
    cpu_period=100_000,
    pids_limit=128,
    tmpfs=_DEFAULT_TMPFS,
    ttl_seconds_max=1_800,
    network_mode="egress-proxied",
    egress_allowlist_required=True,
    cap_drop=("ALL",),
    cap_add=(),
    security_opt=("no-new-privileges:true",),
    read_only=True,
)


PROFILES: Final[Mapping[str, ContainerProfile]] = {
    _DEFAULT_STRICT.name: _DEFAULT_STRICT,
    _MALWARE_SANDBOX.name: _MALWARE_SANDBOX,
    _EGRESS_PROXIED.name: _EGRESS_PROXIED,
    _EGRESS_PROXIED_SIDECAR.name: _EGRESS_PROXIED_SIDECAR,
    _LLM_SANDBOX.name: _LLM_SANDBOX,
}


def get(name: str) -> ContainerProfile:
    """Look up a profile by name; raise ``UnknownProfile`` on miss."""
    try:
        return PROFILES[name]
    except KeyError:
        raise UnknownProfile(name) from None


def names() -> Tuple[str, ...]:
    """Return the registered profile names, sorted."""
    return tuple(sorted(PROFILES))


__all__ = [
    "ContainerProfile",
    "PROFILES",
    "UnknownProfile",
    "get",
    "names",
]
