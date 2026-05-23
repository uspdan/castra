"""Validator plugin registry.

Loads the ``bluerange.validators`` entry-point group at module import
and exposes a single :class:`ValidatorRegistry` instance. The
built-ins (``exact``, ``regex``, ``multi_part``) are registered via
the *same* mechanism (see ``backend/pyproject.toml``) — that's the
contract test for the public plugin surface.

The registry is intentionally simple:

- Validators are constructed once at boot.
- Duplicate names (across entry-point groups, including a built-in
  conflict) raise at load time. Operators see the conflict in the
  startup logs rather than silently picking one.
- Lookup is O(1) and never blocks.

Sandboxing — ``asyncio.timeout`` enforcement, subprocess pool — lives
in :mod:`app.services.validator_sandbox` and runs *around* the call,
not inside the registry. Keeping discovery + dispatch separate makes
both halves independently testable.
"""

from __future__ import annotations

import logging
from importlib import metadata
from typing import Dict, Iterable, Iterator, Mapping, Optional

from bluerange_spec import Validator


_logger = logging.getLogger(__name__)
_ENTRY_POINT_GROUP = "bluerange.validators"


class DuplicateValidator(RuntimeError):
    """Two entry-point providers registered the same validator name."""


class UnknownValidator(LookupError):
    """No validator registered under the requested name."""


class ValidatorRegistry:
    """Holds the resolved validator plugins.

    Construct once via :func:`build_default_registry` (or hand-roll for
    tests) and pass it through dependency injection — never hold a
    module-level mutable singleton in production code paths.
    """

    def __init__(self) -> None:
        self._validators: Dict[str, Validator] = {}

    def register(self, validator: Validator, *, source: str = "manual") -> None:
        name = getattr(validator, "name", None)
        if not isinstance(name, str) or not name:
            raise ValueError(
                f"validator {validator!r} from {source} has no 'name' attribute"
            )
        if name in self._validators:
            existing = self._validators[name]
            raise DuplicateValidator(
                f"validator name conflict: '{name}' registered by "
                f"{type(existing).__module__}.{type(existing).__name__} "
                f"and by {type(validator).__module__}.{type(validator).__name__} "
                f"(source: {source})"
            )
        self._validators[name] = validator

    def get(self, name: str) -> Validator:
        try:
            return self._validators[name]
        except KeyError:
            raise UnknownValidator(
                f"no validator registered under {name!r}; "
                f"known: {sorted(self._validators)}"
            ) from None

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._validators

    def __iter__(self) -> Iterator[str]:
        return iter(self._validators)

    def names(self) -> Iterable[str]:
        return tuple(sorted(self._validators))

    def as_mapping(self) -> Mapping[str, Validator]:
        return dict(self._validators)


def discover_entry_points(
    registry: ValidatorRegistry,
    group: str = _ENTRY_POINT_GROUP,
    *,
    select: Optional[Iterable[str]] = None,
) -> ValidatorRegistry:
    """Load plugins from ``group`` into ``registry``.

    ``select`` — when provided, only entry-point names in the iterable
    are loaded. Used in tests to avoid pulling in third-party plugins
    that happen to be installed in the venv.
    """

    eps = metadata.entry_points()
    found = list(eps.select(group=group)) if hasattr(eps, "select") else list(
        eps.get(group, [])  # type: ignore[union-attr]
    )
    select_set = set(select) if select is not None else None
    for ep in found:
        if select_set is not None and ep.name not in select_set:
            continue
        loaded = ep.load()
        instance = loaded() if isinstance(loaded, type) else loaded
        if not isinstance(instance, Validator):
            raise TypeError(
                f"entry point {ep.name!r} from {ep.value!r} resolved to "
                f"{type(instance).__name__}, expected bluerange_spec.Validator"
            )
        registry.register(instance, source=ep.value)
        # ``name`` is reserved by stdlib LogRecord (it carries the
        # logger name itself) — passing it via ``extra=`` raises
        # ``KeyError: Attempt to overwrite 'name' in LogRecord`` on
        # every call. Rename to ``ep_name`` so the field still
        # surfaces in structured logs without colliding.
        _logger.info(
            "validator_registry.loaded",
            extra={"ep_name": ep.name, "target": ep.value},
        )
    return registry


def build_default_registry() -> ValidatorRegistry:
    """Convenience: empty registry populated from the canonical group."""

    registry = ValidatorRegistry()
    discover_entry_points(registry)
    return registry


_default_registry: Optional[ValidatorRegistry] = None


def get_registry() -> ValidatorRegistry:
    """Return the process-wide registry, building it on first call.

    Lazy initialisation matches the pattern of the other module-level
    services (``audit.append``, ``flag_dispatch.dispatch_submission``).
    Tests that need a different registry monkeypatch this module's
    ``_default_registry`` directly.
    """

    global _default_registry
    if _default_registry is None:
        _default_registry = build_default_registry()
    return _default_registry


def reset_registry() -> None:
    """Clear the cached registry. Test-only — do not call in production."""

    global _default_registry
    _default_registry = None


__all__ = [
    "DuplicateValidator",
    "UnknownValidator",
    "ValidatorRegistry",
    "build_default_registry",
    "discover_entry_points",
    "get_registry",
    "reset_registry",
]
