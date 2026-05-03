"""Bundled seccomp profile loader.

Profiles ship as JSON files alongside this module. ``load_profile(name)``
returns the parsed profile (a ``dict`` ready to hand to docker-py via
``security_opt=["seccomp=<json>"]``). ``validate_all_profiles()`` is
called on application boot from ``app.main`` so a malformed bundled
profile fails the boot loud rather than at instance-launch time.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, Mapping

_HERE: Final = Path(__file__).parent
_REQUIRED_KEYS: Final = ("defaultAction", "syscalls")


class SeccompProfileError(RuntimeError):
    """A bundled seccomp profile is missing or malformed."""


def profile_path(name: str) -> Path:
    """Return the on-disk path of a bundled profile by short name."""
    return _HERE / f"{name}.json"


def load_profile(name: str) -> Mapping[str, object]:
    """Parse a bundled profile by short name.

    Raises ``SeccompProfileError`` on missing file, JSON decode failure,
    or absence of the OCI-required top-level keys.
    """
    path = profile_path(name)
    if not path.is_file():
        raise SeccompProfileError(f"seccomp profile not found: {name} ({path})")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SeccompProfileError(f"seccomp profile {name} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SeccompProfileError(f"seccomp profile {name} must be a JSON object")
    for key in _REQUIRED_KEYS:
        if key not in data:
            raise SeccompProfileError(f"seccomp profile {name} missing required key: {key}")
    return data


def profile_sha256(name: str) -> str:
    """Return the SHA-256 of the on-disk profile bytes (audit trail)."""
    path = profile_path(name)
    if not path.is_file():
        raise SeccompProfileError(f"seccomp profile not found: {name} ({path})")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_all_profiles() -> dict[str, str]:
    """Parse every bundled profile, returning ``{name: sha256}``.

    Called from the FastAPI ``lifespan`` startup. Raises
    ``SeccompProfileError`` on the first malformed profile so boot
    fails fast.
    """
    out: dict[str, str] = {}
    for path in sorted(_HERE.glob("*.json")):
        name = path.stem
        load_profile(name)
        out[name] = profile_sha256(name)
    return out


__all__ = [
    "SeccompProfileError",
    "load_profile",
    "profile_path",
    "profile_sha256",
    "validate_all_profiles",
]
