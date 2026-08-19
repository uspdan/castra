"""Compatibility shim — implementation moved to the Castra SDK.

The validator runtime was extracted to ``castra_spec`` so challenge
authors can run it without installing this backend (see ADR 005 and
the SDK-extraction PR). Explicit named re-exports rather than ``import
*``: mypy resolves them, and the surface this shim promises is written
down instead of implied.
"""

from castra_spec.builtin.exact import (  # noqa: F401
    ExactValidator,
    hash_exact_value,
)
