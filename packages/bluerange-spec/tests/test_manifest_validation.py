"""Manifest validation tests for happy + sad paths."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bluerange_spec import (
    ChallengeManifest,
    ManifestParseError,
    ManifestValidationError,
    load_manifest_text,
)


_MIN_MANIFEST = {
    "spec_version": "1",
    "slug": "soc-001-test",
    "title": "Test",
    "description": "A short description.",
    "team": "blue",
    "category": "SOC",
    "difficulty": 1,
    "points": 100,
    "license": "MIT",
    "author": {"name": "Test Author"},
    "container": {"image": "siege/test", "port": 8080},
    "flags": [{"id": "f1", "type": "exact", "value": "CTF{REDACTED}", "points": 100}],
}


def test_minimum_manifest_validates() -> None:
    m = ChallengeManifest.model_validate(_MIN_MANIFEST)
    assert m.spec_version == "1"
    assert m.slug == "soc-001-test"
    assert len(m.flags) == 1
    assert m.flags[0].type == "exact"


def test_unknown_top_level_field_rejected() -> None:
    bad = {**_MIN_MANIFEST, "extra_field": "nope"}
    with pytest.raises(ValidationError):
        ChallengeManifest.model_validate(bad)


def test_duplicate_flag_ids_rejected() -> None:
    bad = {
        **_MIN_MANIFEST,
        "flags": [
            {"id": "f1", "type": "exact", "value": "a", "points": 50},
            {"id": "f1", "type": "exact", "value": "b", "points": 50},
        ],
    }
    with pytest.raises(ValidationError, match="unique"):
        ChallengeManifest.model_validate(bad)


def test_test_case_referencing_unknown_flag_rejected() -> None:
    bad = {
        **_MIN_MANIFEST,
        "tests": {
            "cases": [
                {
                    "name": "wrong",
                    "flag_id": "missing",
                    "submission": "x",
                    "expected": "pass",
                }
            ]
        },
    }
    with pytest.raises(ValidationError, match="unknown flag"):
        ChallengeManifest.model_validate(bad)


def test_self_prerequisite_rejected() -> None:
    bad = {**_MIN_MANIFEST, "prerequisites": [_MIN_MANIFEST["slug"]]}
    with pytest.raises(ValidationError, match="itself as a prerequisite"):
        ChallengeManifest.model_validate(bad)


def test_regex_flag_compiles() -> None:
    payload = {
        **_MIN_MANIFEST,
        "flags": [
            {"id": "f1", "type": "regex", "pattern": "^CTF\\{[a-z0-9_]+\\}$", "points": 100}
        ],
    }
    m = ChallengeManifest.model_validate(payload)
    assert m.flags[0].type == "regex"


def test_regex_flag_uncompilable_rejected() -> None:
    payload = {
        **_MIN_MANIFEST,
        "flags": [
            {"id": "f1", "type": "regex", "pattern": "[unclosed", "points": 100}
        ],
    }
    with pytest.raises(ValidationError, match="regex does not compile"):
        ChallengeManifest.model_validate(payload)


def test_artifact_path_traversal_rejected() -> None:
    payload = {
        **_MIN_MANIFEST,
        "artifacts": [
            {
                "path": "../../etc/passwd",
                "sha256": "0" * 64,
            }
        ],
    }
    with pytest.raises(ValidationError, match="traverse parents"):
        ChallengeManifest.model_validate(payload)


def test_container_digest_format_enforced() -> None:
    payload = {
        **_MIN_MANIFEST,
        "container": {
            "image": "siege/test",
            "port": 8080,
            # 71 chars but wrong prefix — exercises the format regex
            "digest": "md5:" + "a" * 67,
        },
    }
    with pytest.raises(ValidationError, match="sha256:"):
        ChallengeManifest.model_validate(payload)


def test_load_manifest_text_yaml_round_trip() -> None:
    yaml_text = """
spec_version: "1"
slug: dfir-001-test
title: Test
description: A short description.
team: blue
category: DFIR
difficulty: 2
points: 250
license: MIT
author:
  name: Tester
container:
  image: siege/test
  port: 8080
flags:
  - id: f1
    type: exact
    value: "CTF{REDACTED}"
    points: 250
""".lstrip()
    manifest, raw = load_manifest_text(yaml_text)
    assert manifest.slug == "dfir-001-test"
    assert raw["slug"] == "dfir-001-test"


def test_load_manifest_text_rejects_garbage() -> None:
    with pytest.raises(ManifestParseError):
        load_manifest_text(": : :")


def test_load_manifest_text_validates() -> None:
    with pytest.raises(ManifestValidationError):
        load_manifest_text("spec_version: '1'\nslug: x\n")


def _with_container(**overrides) -> dict:
    base = dict(_MIN_MANIFEST)
    base["container"] = {"image": "siege/test", "port": 8080, **overrides}
    return base


def test_egress_allowlist_accepted_on_egress_proxied_profile() -> None:
    m = ChallengeManifest.model_validate(
        _with_container(
            profile="egress-proxied",
            egress_allowlist=["api.example.com", "registry.example.org"],
        )
    )
    assert m.container.profile == "egress-proxied"
    assert m.container.egress_allowlist == [
        "api.example.com",
        "registry.example.org",
    ]


def test_egress_allowlist_rejected_on_default_strict() -> None:
    with pytest.raises(ValidationError) as exc:
        ChallengeManifest.model_validate(
            _with_container(
                profile="default-strict",
                egress_allowlist=["api.example.com"],
            )
        )
    assert "egress_allowlist" in str(exc.value)


def test_egress_allowlist_rejected_with_implicit_default_profile() -> None:
    with pytest.raises(ValidationError):
        ChallengeManifest.model_validate(
            _with_container(egress_allowlist=["api.example.com"])
        )


def test_egress_allowlist_invalid_fqdn_rejected() -> None:
    with pytest.raises(ValidationError) as exc:
        ChallengeManifest.model_validate(
            _with_container(
                profile="egress-proxied",
                egress_allowlist=["NOT A HOST"],
            )
        )
    assert "FQDN" in str(exc.value) or "valid FQDN" in str(exc.value)


def test_egress_allowlist_lowercases_entries() -> None:
    m = ChallengeManifest.model_validate(
        _with_container(
            profile="egress-proxied",
            egress_allowlist=["API.Example.COM"],
        )
    )
    assert m.container.egress_allowlist == ["api.example.com"]


def test_egress_allowlist_non_string_entry_rejected() -> None:
    with pytest.raises(ValidationError):
        ChallengeManifest.model_validate(
            _with_container(
                profile="egress-proxied",
                egress_allowlist=[123],
            )
        )
