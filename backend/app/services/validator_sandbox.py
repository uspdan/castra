"""Compatibility shim — implementation moved to the Castra SDK.

The validator runtime was extracted to ``castra_spec`` so challenge
authors can run it without installing this backend (see ADR 005 and
the SDK-extraction PR). Explicit named re-exports rather than ``import
*``: mypy resolves them, and the surface this shim promises is written
down instead of implied.
"""

from castra_spec import sandbox as _sandbox
from castra_spec.sandbox import (  # noqa: F401
    readonly_artifact_dir,
    run_validator,
    run_validator_subprocess,
)


def _platform_isolation_policy() -> bool:
    from app.config import get_settings

    return bool(get_settings().VALIDATOR_REQUIRE_NETWORK_ISOLATION)


# Wire the platform's operator setting into the SDK's policy hook at
# import time — every platform consumer gets Settings-driven behaviour;
# standalone SDK users are unaffected because this module only exists
# platform-side.
_sandbox.require_network_isolation_hook = _platform_isolation_policy
