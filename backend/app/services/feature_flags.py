"""Feature-flag registry and evaluation (CLAUDE.md §19).

Flags gate non-trivial features so they can ship dark and be enabled
incrementally. Evaluation is in-memory — it reads the cached
:class:`app.config.Settings`, so there is no per-request I/O — and it
**fails closed**: an unknown flag name, or an override the operator can't
be parsed, resolves to ``False``. A feature gate must never fail open.

Configuration
-------------
Flags are set via the ``FEATURE_FLAGS`` setting (env: ``FEATURE_FLAGS``),
a comma-separated list of ``name=on|off`` pairs::

    FEATURE_FLAGS="FEATURE_API_V1_WRITEUPS=on, FEATURE_CHALLENGES_AI_HONEYPOT=off"

Anything not listed uses the registry default below. Every flag is
declared in :data:`_REGISTRY` with an owner and a removal date so stale
launch gates are visible tech debt rather than mystery conditionals
(CLAUDE.md §19.2).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings

_TRUE_TOKENS = frozenset({"on", "true", "1", "enabled", "yes"})
_FALSE_TOKENS = frozenset({"off", "false", "0", "disabled", "no"})


@dataclass(frozen=True)
class FlagSpec:
    """Metadata for a single feature flag."""

    name: str
    default: bool
    owner: str
    description: str
    # ISO date the flag should be removed by, or "permanent" for ops
    # toggles / kill switches that are expected to live indefinitely.
    removal: str


# Flag naming: FEATURE_<MODULE>_<DESCRIPTION> (CLAUDE.md §19.1).
_REGISTRY: dict[str, FlagSpec] = {
    "FEATURE_API_V1_WRITEUPS": FlagSpec(
        name="FEATURE_API_V1_WRITEUPS",
        default=False,
        owner="platform",
        description="Expose write-ups on the locked /api/v1 contract.",
        removal="2026-12-31",
    ),
    "FEATURE_API_V1_COMPETITIONS": FlagSpec(
        name="FEATURE_API_V1_COMPETITIONS",
        default=False,
        owner="platform",
        description="Expose competitions on the locked /api/v1 contract.",
        removal="2026-12-31",
    ),
    "FEATURE_CHALLENGES_AI_HONEYPOT": FlagSpec(
        name="FEATURE_CHALLENGES_AI_HONEYPOT",
        default=False,
        owner="content",
        description="Enable AI/LLM honeypot validators for challenge authoring.",
        removal="2027-03-31",
    ),
    "FEATURE_ENGAGEMENT_INCIDENT_REPORTS": FlagSpec(
        name="FEATURE_ENGAGEMENT_INCIDENT_REPORTS",
        default=False,
        owner="content",
        description="Graded incident-report analysis for threat-hunt challenges.",
        removal="2027-03-31",
    ),
}


def _parse_overrides(raw: str) -> dict[str, bool]:
    """Parse the ``FEATURE_FLAGS`` string into a ``{name: bool}`` map.

    Malformed tokens (no ``=``, unrecognised value) are skipped rather
    than raised — a typo in ops config must not crash the app, and the
    affected flag simply falls back to its registry default.
    """
    overrides: dict[str, bool] = {}
    for token in raw.split(","):
        token = token.strip()
        if not token or "=" not in token:
            continue
        name, _, value = token.partition("=")
        name = name.strip()
        value = value.strip().lower()
        if value in _TRUE_TOKENS:
            overrides[name] = True
        elif value in _FALSE_TOKENS:
            overrides[name] = False
        # unrecognised value -> ignore, use default
    return overrides


def is_enabled(name: str) -> bool:
    """Return whether feature flag ``name`` is currently on.

    Fails closed: unknown flags return ``False``.
    """
    spec = _REGISTRY.get(name)
    if spec is None:
        return False
    raw = getattr(get_settings(), "FEATURE_FLAGS", "") or ""
    overrides = _parse_overrides(raw)
    return overrides.get(name, spec.default)


def all_flags() -> dict[str, bool]:
    """Return the resolved on/off state of every registered flag."""
    return {name: is_enabled(name) for name in _REGISTRY}


def registered_flags() -> dict[str, FlagSpec]:
    """Return the flag registry (name -> spec) for introspection/admin."""
    return dict(_REGISTRY)
