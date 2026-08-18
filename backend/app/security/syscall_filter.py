"""Compatibility shim — implementation moved to the Castra SDK.

The validator runtime was extracted to ``castra_spec`` so challenge
authors can run it without installing this backend (see ADR 005 and
the SDK-extraction PR). This module re-exports the public surface so
the platform's existing import sites keep working; new platform code
should import from ``castra_spec`` directly.
"""

from castra_spec.syscall_filter import *  # noqa: F401,F403

