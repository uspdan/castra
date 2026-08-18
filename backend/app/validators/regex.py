"""Compatibility shim — implementation moved to the Castra SDK.

The validator runtime was extracted to ``castra_spec`` so challenge
authors can run it without installing this backend (see ADR 005 and
the SDK-extraction PR). This module re-exports the public surface so
the platform's existing import sites keep working; new platform code
should import from ``castra_spec`` directly.
"""

from castra_spec.builtin.regex import *  # noqa: F401,F403
from castra_spec.builtin.regex import RegexValidator  # noqa: F401

# Private helper reached by app.validators.llm_signal (shares the
# re2-with-stdlib-fallback compile path). Underscore names are skipped
# by ``import *``, so it needs an explicit re-export.
from castra_spec.builtin.regex import _compile  # noqa: F401,E402
