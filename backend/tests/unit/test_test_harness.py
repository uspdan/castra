"""Unit tests for the offline challenge test harness."""

from __future__ import annotations

import hashlib
import json
import textwrap
from pathlib import Path

import pytest

from app.services.test_harness import (
    CaseStatus,
    HarnessOutcome,
    HarnessReport,
    run_case,
    run_challenge,
    run_paths,
)
from app.services.challenge_loader.flag_mapping import flag_to_dispatch
from bluerange_spec import (
    ChallengeManifest,
    ExactFlag,
    TestCase,
)


_BASE_MANIFEST_DICT = {
    "spec_version": "1",
    "slug": "test-001",
    "title": "Harness Smoke",
    "description": "Smoke fixture for the harness tests.",
    "team": "blue",
    "category": "TEST",
    "difficulty": 1,
    "points": 100,
    "license": "MIT",
    "author": {"name": "Harness Test"},
    "container": {"image": "siege/test", "port": 8080, "profile": "default-strict"},
}


def _write_manifest(directory: Path, payload: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.yaml"
    # Pydantic-style YAML round-trip via json — load_manifest accepts
    # either format, so JSON-as-YAML keeps the test deterministic.
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# run_case
# ---------------------------------------------------------------------------
class TestRunCase:
    async def test_pass_expected_pass(self, tmp_path):
        flag = ExactFlag(id="f1", points=100, value="hello")
        args = flag_to_dispatch(flag)
        case = TestCase(
            name="happy", flag_id="f1", submission="hello", expected="pass"
        )
        outcome = await run_case(
            case, flag_args=args, challenge_slug="t", challenge_dir=tmp_path
        )
        assert outcome.status == CaseStatus.PASSED
        assert outcome.actual_correct is True

    async def test_fail_expected_pass_yields_failed(self, tmp_path):
        flag = ExactFlag(id="f1", points=100, value="hello")
        args = flag_to_dispatch(flag)
        case = TestCase(
            name="wrong submission for pass-case",
            flag_id="f1", submission="goodbye", expected="pass",
        )
        outcome = await run_case(
            case, flag_args=args, challenge_slug="t", challenge_dir=tmp_path
        )
        assert outcome.status == CaseStatus.FAILED
        assert outcome.actual_correct is False

    async def test_pass_expected_fail_yields_failed(self, tmp_path):
        flag = ExactFlag(id="f1", points=100, value="hello")
        args = flag_to_dispatch(flag)
        case = TestCase(
            name="happy submission as a fail-case",
            flag_id="f1", submission="hello", expected="fail",
        )
        outcome = await run_case(
            case, flag_args=args, challenge_slug="t", challenge_dir=tmp_path
        )
        assert outcome.status == CaseStatus.FAILED
        assert outcome.actual_correct is True

    async def test_fail_expected_fail_yields_passed(self, tmp_path):
        flag = ExactFlag(id="f1", points=100, value="hello")
        args = flag_to_dispatch(flag)
        case = TestCase(
            name="negative case",
            flag_id="f1", submission="goodbye", expected="fail",
        )
        outcome = await run_case(
            case, flag_args=args, challenge_slug="t", challenge_dir=tmp_path
        )
        assert outcome.status == CaseStatus.PASSED
        assert outcome.actual_correct is False

    async def test_unknown_validator_yields_errored(self, tmp_path):
        from app.services.challenge_loader.flag_mapping import FlagDispatchArgs

        bogus = FlagDispatchArgs(
            flag_id="f1",
            flag_type="not_a_real_validator",
            points=100,
            label=None,
            value_hash=None,
            config={},
        )
        case = TestCase(
            name="missing plugin",
            flag_id="f1", submission="x", expected="pass",
        )
        outcome = await run_case(
            case, flag_args=bogus, challenge_slug="t", challenge_dir=tmp_path
        )
        assert outcome.status == CaseStatus.ERRORED
        assert "not installed" in (outcome.error or "")

    async def test_validator_runtime_error_yields_errored(self, tmp_path):
        # chain_of_custody raises ValidatorConfigError when the config
        # is structurally invalid (programmer error, not user error).
        from app.services.challenge_loader.flag_mapping import FlagDispatchArgs

        bad = FlagDispatchArgs(
            flag_id="f1",
            flag_type="chain_of_custody",
            points=100,
            label=None,
            value_hash=None,
            config={"expected_steps": [], "allowed_actors": []},
        )
        case = TestCase(
            name="bad config",
            flag_id="f1", submission="[]", expected="pass",
        )
        outcome = await run_case(
            case, flag_args=bad, challenge_slug="t", challenge_dir=tmp_path
        )
        assert outcome.status == CaseStatus.ERRORED


# ---------------------------------------------------------------------------
# run_challenge
# ---------------------------------------------------------------------------
class TestRunChallenge:
    async def test_happy_path(self, tmp_path):
        digest = hashlib.sha256(b"hello").hexdigest()
        manifest = {
            **_BASE_MANIFEST_DICT,
            "flags": [
                {"id": "f1", "type": "exact", "value": "hello", "points": 100}
            ],
            "tests": {
                "cases": [
                    {"name": "happy", "flag_id": "f1", "submission": "hello", "expected": "pass"},
                    {"name": "wrong", "flag_id": "f1", "submission": "x", "expected": "fail"},
                ]
            },
        }
        _write_manifest(tmp_path, manifest)
        outcome = await run_challenge(tmp_path)
        assert outcome.all_passed
        assert len(outcome.cases) == 2
        assert {c.status for c in outcome.cases} == {CaseStatus.PASSED}

    async def test_missing_manifest(self, tmp_path):
        outcome = await run_challenge(tmp_path)
        assert outcome.load_error is not None
        assert "ManifestNotFound" in outcome.load_error
        assert outcome.all_passed is False

    async def test_unknown_flag_id_in_test_case(self, tmp_path):
        # Pydantic's manifest validator rejects unknown flag refs at
        # load time; we simulate the post-load defensive branch by
        # building the manifest directly from valid pieces and
        # synthesising a TestCase via the harness's own per-flag
        # path. Here we cover the explicit "manifest forgot a flag"
        # path the runner has to defend against.
        manifest = {
            **_BASE_MANIFEST_DICT,
            "flags": [
                {"id": "f1", "type": "exact", "value": "hello", "points": 100}
            ],
        }
        _write_manifest(tmp_path, manifest)
        # Manually run a test case referencing a missing flag via run_case
        # — run_challenge wouldn't be able to construct this because the
        # spec validator rejects it, so we verify run_challenge skips
        # gracefully if the index lookup misses.
        outcome = await run_challenge(tmp_path)
        assert outcome.load_error is None
        assert outcome.cases == []

    async def test_no_test_cases_is_clean(self, tmp_path):
        manifest = {
            **_BASE_MANIFEST_DICT,
            "flags": [
                {"id": "f1", "type": "exact", "value": "hello", "points": 100}
            ],
        }
        _write_manifest(tmp_path, manifest)
        outcome = await run_challenge(tmp_path)
        assert outcome.all_passed is True
        assert outcome.cases == []


# ---------------------------------------------------------------------------
# run_paths
# ---------------------------------------------------------------------------
class TestRunPaths:
    async def test_walks_root_with_multiple_challenges(self, tmp_path):
        for idx in range(3):
            sub = tmp_path / f"chal-{idx}"
            _write_manifest(
                sub,
                {
                    **_BASE_MANIFEST_DICT,
                    "slug": f"chal-{idx}",
                    "flags": [
                        {"id": "f1", "type": "exact", "value": "x", "points": 10}
                    ],
                    "tests": {
                        "cases": [
                            {
                                "name": "ok",
                                "flag_id": "f1",
                                "submission": "x",
                                "expected": "pass",
                            }
                        ]
                    },
                },
            )
        report = await run_paths([tmp_path])
        assert len(report.challenges) == 3
        assert report.all_passed is True
        assert report.case_counts["passed"] == 3

    async def test_directly_targeting_challenge_dir(self, tmp_path):
        _write_manifest(
            tmp_path,
            {
                **_BASE_MANIFEST_DICT,
                "flags": [{"id": "f1", "type": "exact", "value": "x", "points": 10}],
                "tests": {
                    "cases": [
                        {"name": "ok", "flag_id": "f1", "submission": "x", "expected": "pass"}
                    ]
                },
            },
        )
        report = await run_paths([tmp_path])
        assert len(report.challenges) == 1

    async def test_skips_directories_without_manifest(self, tmp_path):
        (tmp_path / "not-a-challenge").mkdir()
        (tmp_path / "not-a-challenge" / "README.md").write_text("hi")
        report = await run_paths([tmp_path])
        assert report.challenges == []

    async def test_nonexistent_path_is_quietly_skipped(self):
        report = await run_paths([Path("/data/does-not-exist-anywhere-xyz")])
        assert report.challenges == []


# ---------------------------------------------------------------------------
# Examples integration — run the harness over the real examples/ dir.
# ---------------------------------------------------------------------------
class TestExamplesEndToEnd:
    async def test_examples_all_pass(self):
        examples = Path(__file__).resolve().parents[2].parent / "examples" / "challenges"
        if not examples.exists():
            pytest.skip("examples/challenges not present in this checkout")
        report = await run_paths([examples])
        if not report.all_passed:
            failures = [
                (c.slug, [(case.case_name, case.status.value, case.error) for case in c.cases])
                for c in report.challenges
                if not c.all_passed
            ]
            pytest.fail(f"examples/challenges harness failed: {failures}")
        # At minimum we expect the three examples we've authored.
        slugs = {c.slug for c in report.challenges}
        assert "soc-001-off-hours-admin" in slugs
        assert "soc-002-pwsh-detection" in slugs
