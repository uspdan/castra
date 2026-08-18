"""Compatibility shim — implementation moved to the Castra SDK.

The validator runtime was extracted to ``castra_spec`` so challenge
authors can run it without installing this backend (see ADR 005 and
the SDK-extraction PR). Explicit named re-exports rather than ``import
*``: mypy resolves them, and the surface this shim promises is written
down instead of implied.
"""

from castra_spec.registry import (  # noqa: F401
    DuplicateValidator,
    UnknownValidator,
    ValidatorRegistry,
    build_default_registry,
    discover_entry_points,
    get_registry,
    reset_registry,
)
from castra_spec.registry import _ENTRY_POINT_GROUP  # noqa: F401 — tests reach for it
