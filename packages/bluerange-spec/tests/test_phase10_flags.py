"""Validation tests for the Phase 10 blue-team flag types.

The five new flag classes — sigma_rule, yara_rule, chain_of_custody,
attack_chain, cloud_misconfig — must round-trip through the
discriminated-union ``Flag`` and validate their per-field constraints.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from bluerange_spec import (
    AttackChainFlag,
    ChainOfCustodyFlag,
    ChallengeManifest,
    CloudMisconfigFlag,
    SigmaRuleFlag,
    YaraRuleFlag,
)


_BASE_MANIFEST = {
    "spec_version": "1",
    "slug": "blue-001-detect",
    "title": "Detect PowerShell",
    "description": "Write a Sigma rule.",
    "team": "blue",
    "category": "SOC",
    "difficulty": 2,
    "points": 200,
    "license": "MIT",
    "author": {"name": "Test Author"},
    "container": {"image": "siege/blue", "port": 8080},
}


# ---------------------------------------------------------------------------
# sigma_rule
# ---------------------------------------------------------------------------
def test_sigma_rule_flag_validates() -> None:
    m = ChallengeManifest.model_validate(
        {
            **_BASE_MANIFEST,
            "flags": [
                {
                    "id": "f1",
                    "type": "sigma_rule",
                    "points": 100,
                    "events_filename": "events.json",
                    "expected_match_indices": [0, 2, 4],
                    "require_logsource": {
                        "category": "process_creation",
                        "product": "windows",
                    },
                }
            ],
        }
    )
    assert isinstance(m.flags[0], SigmaRuleFlag)
    assert m.flags[0].expected_match_indices == [0, 2, 4]


def test_sigma_rule_negative_indices_rejected() -> None:
    with pytest.raises(ValidationError):
        SigmaRuleFlag(
            id="f1", points=10, events_filename="e.json",
            expected_match_indices=[-1],
        )


def test_sigma_rule_unknown_logsource_key_rejected() -> None:
    with pytest.raises(ValidationError):
        SigmaRuleFlag(
            id="f1", points=10, events_filename="e.json",
            expected_match_indices=[0],
            require_logsource={"unknown_key": "x"},
        )


# ---------------------------------------------------------------------------
# yara_rule
# ---------------------------------------------------------------------------
def test_yara_rule_flag_validates() -> None:
    f = YaraRuleFlag(
        id="f1", points=100,
        samples_dir="samples",
        expected_matches=["evil.bin"],
        expected_no_match=["clean.bin"],
    )
    assert f.samples_dir == "samples"


def test_yara_rule_path_traversal_rejected() -> None:
    with pytest.raises(ValidationError):
        YaraRuleFlag(
            id="f1", points=10, expected_matches=["../etc/passwd"],
        )
    with pytest.raises(ValidationError):
        YaraRuleFlag(
            id="f1", points=10, samples_dir="../up", expected_matches=["a.bin"],
        )


# ---------------------------------------------------------------------------
# chain_of_custody
# ---------------------------------------------------------------------------
def test_chain_of_custody_validates() -> None:
    f = ChainOfCustodyFlag(
        id="f1", points=50,
        expected_steps=["acquire", "transport"],
        allowed_actors=["alice", "bob"],
        expected_final_hash="0" * 64,
    )
    assert len(f.expected_steps) == 2


def test_chain_of_custody_bad_final_hash_rejected() -> None:
    with pytest.raises(ValidationError):
        ChainOfCustodyFlag(
            id="f1", points=50,
            expected_steps=["acquire"],
            allowed_actors=["alice"],
            expected_final_hash="not-hex",
        )


# ---------------------------------------------------------------------------
# attack_chain
# ---------------------------------------------------------------------------
def test_attack_chain_validates() -> None:
    f = AttackChainFlag(
        id="f1", points=50,
        required_chain=["t1566.001", "T1059", "T1486"],
    )
    # Validator normalises to upper case.
    assert f.required_chain == ["T1566.001", "T1059", "T1486"]


def test_attack_chain_bad_technique_rejected() -> None:
    with pytest.raises(ValidationError):
        AttackChainFlag(id="f1", points=50, required_chain=["bogus"])


# ---------------------------------------------------------------------------
# cloud_misconfig
# ---------------------------------------------------------------------------
def test_cloud_misconfig_validates() -> None:
    f = CloudMisconfigFlag(
        id="f1", points=50,
        expected_findings=[
            {"resource": "aws_s3_bucket.x", "finding": "PUBLIC", "severity": "critical"},
            {"resource": "aws_sg.y", "finding": "OPEN_22", "severity": "high"},
        ],
        must_include_severities=["critical"],
    )
    assert len(f.expected_findings) == 2
    assert f.expected_findings[0].severity == "critical"


def test_cloud_misconfig_finding_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        CloudMisconfigFlag(
            id="f1", points=50,
            expected_findings=[
                {"resource": "x", "finding": "y", "extra_field": "z"},
            ],
        )


# ---------------------------------------------------------------------------
# Discriminated union dispatch — manifest.flags accepts each new type.
# ---------------------------------------------------------------------------
def test_discriminator_dispatches_each_new_type() -> None:
    m = ChallengeManifest.model_validate(
        {
            **_BASE_MANIFEST,
            "flags": [
                {
                    "id": "f1", "type": "yara_rule", "points": 50,
                    "expected_matches": ["evil.bin"],
                },
                {
                    "id": "f2", "type": "chain_of_custody", "points": 50,
                    "expected_steps": ["acquire"],
                    "allowed_actors": ["alice"],
                },
                {
                    "id": "f3", "type": "attack_chain", "points": 50,
                    "required_chain": ["T1566.001"],
                },
                {
                    "id": "f4", "type": "cloud_misconfig", "points": 50,
                    "expected_findings": [
                        {"resource": "x", "finding": "y"},
                    ],
                },
            ],
        }
    )
    types = [type(f).__name__ for f in m.flags]
    assert types == [
        "YaraRuleFlag",
        "ChainOfCustodyFlag",
        "AttackChainFlag",
        "CloudMisconfigFlag",
    ]
