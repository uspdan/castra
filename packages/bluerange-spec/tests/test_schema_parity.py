"""Parity test between the Pydantic model and the frozen JSON Schema.

The Pydantic model is the source of truth. The frozen JSON Schema in
``schemas/manifest.schema.json`` is a generated mirror used by editor
integrations (yaml-language-server, IDE plugins, schema validators).
This test refuses to pass when the two have drifted, forcing authors
to regenerate the JSON Schema before merging changes.

Regenerate via the snippet documented in the repo-root spec doc
(docs/challenge-spec-v1.md, "Regenerating the JSON Schema").
"""

from __future__ import annotations

from bluerange_spec import ChallengeManifest
from bluerange_spec.schemas import load_schema


_INJECTED_KEYS = {"$schema", "$id", "title", "description"}


def test_frozen_schema_matches_pydantic_model() -> None:
    generated = ChallengeManifest.model_json_schema()
    frozen = load_schema("manifest")

    # Strip injected metadata so we compare structure-vs-structure.
    frozen_body = {k: v for k, v in frozen.items() if k not in _INJECTED_KEYS}
    generated_body = {k: v for k, v in generated.items() if k not in _INJECTED_KEYS}

    assert frozen_body == generated_body, (
        "frozen JSON schema is out of sync with ChallengeManifest. "
        "Regenerate per the docstring of this test."
    )


def test_frozen_schema_metadata_present() -> None:
    frozen = load_schema("manifest")
    assert frozen.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert "manifest.schema.json" in frozen.get("$id", "")
    assert frozen.get("title") == "BluerangeChallengeManifest"
