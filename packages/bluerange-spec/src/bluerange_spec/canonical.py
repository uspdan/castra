"""Canonical serialisation + content hashing.

`manifest_sha256` is the platform's drift detector: any change to the
canonical bytes of a manifest produces a new digest, which the loader
uses to flag the challenge as ``pending_review`` until an operator
re-releases it.

The canonical form is JSON with sorted keys, no whitespace, ensure_ascii
disabled, separators ``(",", ":")``. We intentionally do **not** use
JCS (RFC 8785) here — sorted-keys JSON is enough for byte-stable hashing
of structures we control, and pulling in a dependency for it is not
warranted in v1.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json(obj: Any) -> bytes:
    """Return canonical JSON bytes for ``obj``.

    Sorted keys, no whitespace, UTF-8 encoded.
    """

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_default,
    ).encode("utf-8")


def manifest_sha256(obj: Any) -> str:
    """SHA-256 hex digest of ``obj`` in canonical form."""

    return hashlib.sha256(canonical_json(obj)).hexdigest()


def sha256_file(path: Path, chunk_size: int = 65536) -> str:
    """SHA-256 hex digest of the bytes of ``path``."""

    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _default(value: Any) -> Any:
    # Allows hashing of pathlib.Path, sets, and other obvious types
    # without forcing callers to pre-convert. Pydantic models should be
    # dumped via ``model.model_dump(mode="json")`` before being passed
    # in — that's the loader's responsibility, not this module's.
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON-serialisable")
