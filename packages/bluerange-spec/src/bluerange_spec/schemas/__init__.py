"""Frozen JSON Schema documents for editor / tooling use.

The Pydantic models in :mod:`bluerange_spec.manifest` are the source of
truth for validation. The JSON Schema files in this directory are a
generated mirror, kept in sync by a parity test in
``packages/bluerange-spec/tests/test_schema_parity.py``. Edit the
Pydantic models, then regenerate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


_SCHEMA_DIR = Path(__file__).parent


def load_schema(name: str = "manifest") -> Dict[str, Any]:
    """Load a frozen JSON Schema document by short name."""

    path = _SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))
