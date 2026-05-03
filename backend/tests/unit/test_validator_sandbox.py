"""Unit tests for the validator sandbox primitives."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Mapping

import pytest

from app.services.validator_sandbox import (
    readonly_artifact_dir,
    run_validator,
    run_validator_subprocess,
)
from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorTimeoutError,
)


@pytest.fixture
def context():
    return ValidationContext(flag_id="f1", challenge_slug="c1")


class _SlowValidator(Validator):
    name = "slow"
    default_timeout_s = 0.05

    async def validate(self, submission, config, context):
        await asyncio.sleep(1.0)
        return ValidationResult(correct=True)


class _FastValidator(Validator):
    name = "fast"
    default_timeout_s = 5.0

    async def validate(self, submission, config, context):
        return ValidationResult(correct=submission == "ok")


class _SubprocessValidator(Validator):
    name = "wants_subprocess"
    requires_subprocess = True

    async def validate(self, submission, config, context):  # pragma: no cover
        return ValidationResult(correct=True)


class TestRunValidatorTimeout:
    async def test_timeout_raises_validator_timeout_error(self, context):
        v = _SlowValidator()
        with pytest.raises(ValidatorTimeoutError):
            await run_validator(v, "anything", {}, context)

    async def test_fast_validator_returns_result(self, context):
        v = _FastValidator()
        result = await run_validator(v, "ok", {}, context)
        assert result.correct is True

    async def test_explicit_override_tightens_budget(self, context):
        v = _FastValidator()
        # _FastValidator returns immediately, so any tiny timeout
        # works — assert the kwarg path is wired without raising.
        result = await run_validator(v, "ok", {}, context, timeout_s=0.5)
        assert result.correct is True

    async def test_requires_subprocess_branch_routes_to_subprocess_runner(self, context):
        # Phase 10: ``requires_subprocess=True`` validators run inside
        # the resource-limited subprocess pool. The subprocess path is
        # exercised end-to-end in ``test_validator_subprocess_sandbox``;
        # here we just assert the dispatch wires through (the in-tree
        # ``_SubprocessValidator`` returns correct=True from its
        # validate body, so a successful subprocess call returns True).
        v = _SubprocessValidator()
        result = await run_validator(v, "x", {}, context)
        assert result.correct is True

    async def test_subprocess_helper_executes_directly(self, context):
        v = _SubprocessValidator()
        result = await run_validator_subprocess(v, "x", {}, context, timeout_s=10.0)
        assert result.correct is True


class TestReadonlyArtifactDir:
    async def test_yields_readable_copy(self, tmp_path):
        source = tmp_path / "artefacts"
        source.mkdir()
        (source / "evidence.log").write_text("login success at 02:14\n")

        async with readonly_artifact_dir(source) as ro:
            target = ro / "evidence.log"
            assert target.read_text() == "login success at 02:14\n"

    async def test_files_are_readonly(self, tmp_path):
        source = tmp_path / "artefacts"
        source.mkdir()
        f = source / "evidence.log"
        f.write_text("x")

        async with readonly_artifact_dir(source) as ro:
            target = ro / "evidence.log"
            mode = os.stat(target).st_mode & 0o777
            # 0o444 (file) — no write bits anywhere, no execute bits
            assert mode & 0o222 == 0
            with pytest.raises(PermissionError):
                target.write_text("mutated")

    async def test_directory_is_readonly(self, tmp_path):
        source = tmp_path / "artefacts"
        source.mkdir()
        (source / "a.txt").write_text("a")

        async with readonly_artifact_dir(source) as ro:
            mode = os.stat(ro).st_mode & 0o777
            # 0o555 — readable + executable for traversal, no writes
            assert mode & 0o222 == 0

    async def test_cleanup_removes_tree(self, tmp_path):
        source = tmp_path / "artefacts"
        source.mkdir()
        (source / "a.txt").write_text("a")

        async with readonly_artifact_dir(source) as ro:
            captured = ro
            assert captured.exists()
        # On exit the temp tree should be removed despite the readonly
        # bits — the cleanup handler restores write perms before unlink.
        assert not captured.exists()
