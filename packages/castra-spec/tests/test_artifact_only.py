"""Spec v1.1 (ADR 005): ``container`` is optional.

A manifest with no container is artifact-only — the platform serves the
declared artifacts and skips the orchestrator. The spec's job is to
make the invalid states unrepresentable: no container *and* no
artifacts is a challenge with no content, rejected at parse time.
"""

from __future__ import annotations

import pytest

from castra_spec import ChallengeManifest


def _manifest(**overrides) -> dict:
    base = {
        "spec_version": "1",
        "slug": "artifact-only-demo",
        "title": "Demo",
        "description": "d",
        "team": "blue",
        "category": "Threat Hunting",
        "difficulty": 1,
        "points": 100,
        "license": "MIT",
        "author": {"name": "t"},
        "flags": [
            {"id": "f1", "type": "exact", "value": "CTF" + "{x}", "points": 100}
        ],
        "artifacts": [
            {"path": "artifacts/a.log", "sha256": "0" * 64, "size_bytes": 10}
        ],
    }
    base.update(overrides)
    return base


class TestContainerOptional:
    def test_no_container_with_artifacts_is_valid(self):
        m = ChallengeManifest.model_validate(_manifest())
        assert m.container is None
        assert len(m.artifacts) == 1

    def test_no_container_and_no_artifacts_is_rejected(self):
        with pytest.raises(Exception) as exc:
            ChallengeManifest.model_validate(_manifest(artifacts=[]))
        assert "at least one artifact" in str(exc.value)

    def test_container_challenges_still_validate_unchanged(self):
        m = ChallengeManifest.model_validate(
            _manifest(
                container={"image": "alpine:3.19", "port": 8080},
                artifacts=[],
            )
        )
        assert m.container is not None
        assert m.container.image == "alpine:3.19"

    def test_container_plus_artifacts_is_valid(self):
        # A live challenge that also ships a pcap — both surfaces at once.
        m = ChallengeManifest.model_validate(
            _manifest(container={"image": "alpine:3.19", "port": 8080})
        )
        assert m.container is not None
        assert m.artifacts


class TestSchemaReflectsOptionality:
    def test_frozen_schema_does_not_require_container(self):
        from castra_spec.schemas import load_schema

        schema = load_schema("manifest")
        assert "container" not in schema.get("required", []), (
            "the frozen JSON Schema still lists container as required — "
            "regenerate it per docs/challenge-spec-v1.md"
        )
