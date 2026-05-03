"""Refusal layer: reject docker-py kwargs that would break the sandbox.

The launcher composes its kwargs purely from a frozen profile, so a
forbidden field can only enter the path through a manifest field the
profile doesn't manage or through future code drift. ``enforce_no_forbidden``
is the runtime guard; tests assert that every forbidden field is caught
even if a manifest tries to sneak it in.
"""

from __future__ import annotations

from typing import Any, Final, Iterable, Mapping


class ForbiddenContainerOption(ValueError):
    """A docker-py kwarg violates the sandbox boundary."""


_FORBIDDEN_TRUTHY_KEYS: Final = (
    "privileged",
    "binds",
    "volumes_from",
)


_FORBIDDEN_NETWORK_MODES: Final = frozenset({"host"})
_FORBIDDEN_PID_MODES: Final = frozenset({"host"})
_FORBIDDEN_IPC_MODES: Final = frozenset({"host"})
_FORBIDDEN_USERNS_MODES: Final = frozenset({"host"})


_FORBIDDEN_CAPS: Final = frozenset(
    {
        "SYS_ADMIN",
        "SYS_MODULE",
        "SYS_PTRACE",
        "SYS_RAWIO",
        "SYS_BOOT",
        "NET_ADMIN",
        "MAC_ADMIN",
        "MAC_OVERRIDE",
        "DAC_READ_SEARCH",
    }
)


_FORBIDDEN_HOST_PATHS: Final = (
    "/var/run/docker.sock",
    "/var/run",
    "/proc",
    "/sys",
    "/dev",
    "/etc",
    "/",
)


def _check_truthy_keys(spec: Mapping[str, Any]) -> None:
    for key in _FORBIDDEN_TRUTHY_KEYS:
        if spec.get(key):
            raise ForbiddenContainerOption(f"{key} is forbidden")


def _check_string_modes(spec: Mapping[str, Any]) -> None:
    pairs = (
        ("network_mode", _FORBIDDEN_NETWORK_MODES),
        ("pid_mode", _FORBIDDEN_PID_MODES),
        ("ipc_mode", _FORBIDDEN_IPC_MODES),
        ("userns_mode", _FORBIDDEN_USERNS_MODES),
    )
    for key, banned in pairs:
        value = spec.get(key)
        if value is None:
            continue
        if value in banned:
            raise ForbiddenContainerOption(f"{key}={value!r} is forbidden")


def _check_caps(spec: Mapping[str, Any]) -> None:
    cap_add: Iterable[str] = spec.get("cap_add") or ()
    bad = {c.upper() for c in cap_add} & _FORBIDDEN_CAPS
    if bad:
        raise ForbiddenContainerOption(
            f"cap_add includes forbidden capabilities: {sorted(bad)}"
        )


def _check_volumes(spec: Mapping[str, Any]) -> None:
    volumes = spec.get("volumes") or {}
    if not isinstance(volumes, Mapping):
        # docker-py accepts list form for read-only binds; refuse the legacy
        # syntax to keep the surface narrow.
        raise ForbiddenContainerOption("volumes must be a mapping or absent")
    for host_path in volumes:
        if not isinstance(host_path, str):
            raise ForbiddenContainerOption("volumes keys must be strings")
        normalised = host_path.rstrip("/") or "/"
        for forbidden in _FORBIDDEN_HOST_PATHS:
            if normalised == forbidden or normalised.startswith(forbidden + "/"):
                raise ForbiddenContainerOption(
                    f"host bind to {host_path!r} is forbidden"
                )


def enforce_no_forbidden(spec: Mapping[str, Any]) -> None:
    """Raise ``ForbiddenContainerOption`` if any forbidden field is set.

    The launcher calls this after composing the final docker-py kwargs
    from the profile. It is also called in tests with hand-rolled
    dictionaries to assert each refusal.
    """
    _check_truthy_keys(spec)
    _check_string_modes(spec)
    _check_caps(spec)
    _check_volumes(spec)


__all__ = [
    "ForbiddenContainerOption",
    "enforce_no_forbidden",
]
