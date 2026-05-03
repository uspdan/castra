"""Child-process entrypoint for ``requires_subprocess=True`` validators.

Run as ``python -m app.services.validator_subprocess_runner``. The
parent (``run_validator_subprocess`` in :mod:`validator_sandbox`) writes
a single JSON envelope on stdin describing the call; this module
unmarshals it, locates the validator class via
``importlib.import_module`` + ``getattr``, runs the validator's coroutine
inside a fresh event loop, and writes a single JSON envelope on stdout.

The child also drops privileges via :mod:`resource` rlimits *before*
importing the validator module so a malicious / buggy plugin can't
escape the budget by allocating a lot of memory at import time. The
parent passes the resource limits in the envelope so the same code
path runs on hosts where ``resource`` is unavailable (Windows CI) — the
parent is responsible for declining to spawn there.

The protocol is intentionally line-based JSON, not pickle: pickle would
be a code-execution channel back into the parent if a child were ever
compromised, while JSON is type-restricted to primitives + nested
dict/list. The :class:`bluerange_spec.ValidationContext` and
:class:`ValidationResult` are reconstructed from primitives on each
side.

Failure modes:

- Validator raises :class:`ValidatorConfigError`: child writes
  ``{"ok": false, "error": "config", "message": ...}``; parent re-raises.
- Validator raises any other exception: child writes
  ``{"ok": false, "error": "internal", "message": ..., "type": ...}``;
  parent re-raises a :class:`ValidatorError`.
- Subprocess exceeds RLIMIT_CPU: kernel sends SIGXCPU; parent's
  ``asyncio.wait_for`` also fires the wall-clock timeout as a
  belt-and-braces guard.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Mapping

# We deliberately import ``resource`` lazily — on Windows the module
# does not exist. The parent declines to spawn on platforms without
# resource.setrlimit, so the import-error path here is never reached
# in supported deployments. The guard is here so module load doesn't
# blow up on contributors running ``python -m`` directly on Windows
# during local debugging.
try:
    import resource  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — POSIX-only
    resource = None  # type: ignore[assignment]


_RLIMITS_KEY = "rlimits"


def _apply_rlimits(rlimits: Mapping[str, int]) -> None:
    """Apply RLIMIT_* values from the parent envelope.

    Each entry is the symbolic name (e.g. ``"RLIMIT_CPU"``) mapping to
    a single integer treated as both soft and hard limit. The kernel
    enforces hard <= existing-hard, so the parent must run with
    permissive limits for these to take effect.
    """

    if resource is None:
        return
    for name, value in rlimits.items():
        rkey = getattr(resource, name, None)
        if rkey is None:
            continue
        try:
            resource.setrlimit(rkey, (int(value), int(value)))
        except (ValueError, OSError):
            # Some limits cannot be raised once dropped (RLIMIT_NOFILE
            # on macOS) or are unavailable on the running kernel. The
            # parent set sensible bounds; if a single rlimit can't be
            # applied we proceed rather than aborting the whole call.
            continue


def _build_context(payload: Mapping[str, Any]):
    from bluerange_spec import ValidationContext

    artifact_raw = payload.get("artifact_dir")
    artifact_dir = Path(artifact_raw) if artifact_raw else None
    metadata = payload.get("submission_metadata") or {}
    return ValidationContext(
        flag_id=str(payload["flag_id"]),
        challenge_slug=str(payload["challenge_slug"]),
        artifact_dir=artifact_dir,
        submission_metadata=dict(metadata),
    )


def _result_to_envelope(result) -> dict[str, Any]:
    return {
        "ok": True,
        "result": {
            "correct": bool(result.correct),
            "partial": bool(getattr(result, "partial", False)),
            "details": dict(result.details or {}),
        },
    }


async def _run_validator(envelope: Mapping[str, Any]) -> dict[str, Any]:
    from bluerange_spec import ValidatorConfigError, ValidatorError

    module_name = str(envelope["validator_module"])
    class_name = str(envelope["validator_class"])
    submission = str(envelope["submission"])
    config = dict(envelope.get("config") or {})
    context = _build_context(envelope.get("context") or {})

    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    validator = cls()
    try:
        result = await validator.validate(submission, config, context)
    except ValidatorConfigError as exc:
        return {"ok": False, "error": "config", "message": str(exc)}
    except ValidatorError as exc:
        return {"ok": False, "error": "validator", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 — surface as structured error
        return {
            "ok": False,
            "error": "internal",
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=4),
        }
    return _result_to_envelope(result)


def main() -> int:
    raw = sys.stdin.read()
    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.stdout.write(
            json.dumps({"ok": False, "error": "envelope", "message": str(exc)})
        )
        return 2

    rlimits = envelope.get(_RLIMITS_KEY) or {}
    _apply_rlimits(rlimits)

    # Refuse to follow the executor's environment into the child by
    # default; only the variables the parent explicitly forwarded
    # (PATH, LANG, etc.) survive. We still allow a final scrub here as
    # defence-in-depth.
    for key in list(os.environ):
        if key.startswith("AWS_") or key.startswith("GOOGLE_") or key in {
            "DATABASE_URL",
            "REDIS_URL",
            "SECRET_KEY",
            "ADMIN_PASSWORD",
        }:
            os.environ.pop(key, None)

    response = asyncio.run(_run_validator(envelope))
    sys.stdout.write(json.dumps(response))
    return 0 if response.get("ok") else 1


if __name__ == "__main__":  # pragma: no cover — exercised via subprocess
    sys.exit(main())
