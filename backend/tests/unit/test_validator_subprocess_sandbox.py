"""Unit tests for the subprocess validator sandbox.

These tests exercise ``run_validator_subprocess`` with a small in-tree
fake validator. They cover happy path, JSON envelope errors,
ValidatorConfigError propagation, internal-error wrapping, and the
wall-clock timeout path. RLIMIT_CPU / RLIMIT_AS kernel kills are
exercised indirectly via the timeout path so we don't need to load
heavy fixtures.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from app.services.validator_sandbox import run_validator_subprocess
from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
    ValidatorError,
    ValidatorTimeoutError,
)


@pytest.fixture
def context():
    return ValidationContext(flag_id="f1", challenge_slug="c1")


# These fakes live in the test module — the subprocess runner imports
# them by ``__module__`` + ``__class__.__name__``. The test runner
# preserves the module on sys.path so the child can resolve them.


class _SubprocessOK(Validator):
    name = "_subproc_ok"
    requires_subprocess = True
    default_timeout_s = 5.0

    async def validate(self, submission, config, context):
        return ValidationResult(
            correct=submission == "yes",
            details={"echo": str(config.get("echo", ""))},
        )


class _SubprocessBadConfig(Validator):
    name = "_subproc_bad"
    requires_subprocess = True
    default_timeout_s = 5.0

    async def validate(self, submission, config, context):
        raise ValidatorConfigError("bad config from child")


class _SubprocessRaises(Validator):
    name = "_subproc_raises"
    requires_subprocess = True
    default_timeout_s = 5.0

    async def validate(self, submission, config, context):
        raise RuntimeError("kaboom")


class _SubprocessHangs(Validator):
    name = "_subproc_hangs"
    requires_subprocess = True
    default_timeout_s = 0.3

    async def validate(self, submission, config, context):
        import time

        time.sleep(30)
        return ValidationResult(correct=True)


class _ArtifactProbe(Validator):
    """Defined at module level so the child subprocess can re-import it.

    A class defined inside a test function exists only in the parent's
    process state — the child re-executes the module's top level and
    never runs the function body, so the class wouldn't exist there.
    """

    name = "_artifact_probe"
    requires_subprocess = True
    default_timeout_s = 5.0

    async def validate(self, submission, config, context):
        return ValidationResult(correct=str(context.artifact_dir) == submission)


class TestRunValidatorSubprocess:
    async def test_happy_path_returns_result(self, context):
        v = _SubprocessOK()
        result = await run_validator_subprocess(
            v, "yes", {"echo": "hello"}, context, timeout_s=10.0
        )
        assert result.correct is True
        assert result.details["echo"] == "hello"

    async def test_wrong_answer_returns_false(self, context):
        v = _SubprocessOK()
        result = await run_validator_subprocess(
            v, "no", {}, context, timeout_s=10.0
        )
        assert result.correct is False

    async def test_config_error_propagates(self, context):
        v = _SubprocessBadConfig()
        with pytest.raises(ValidatorConfigError, match="bad config from child"):
            await run_validator_subprocess(v, "x", {}, context, timeout_s=10.0)

    async def test_internal_error_wrapped(self, context):
        v = _SubprocessRaises()
        with pytest.raises(ValidatorError):
            await run_validator_subprocess(v, "x", {}, context, timeout_s=10.0)

    async def test_timeout_raises_validator_timeout(self, context):
        v = _SubprocessHangs()
        with pytest.raises(ValidatorTimeoutError):
            await run_validator_subprocess(v, "x", {}, context, timeout_s=0.5)

    async def test_artifact_dir_passed_to_child(self, tmp_path, context):
        # Child sees ValidationContext.artifact_dir reconstructed from
        # the parent's primitive payload.
        ctx = ValidationContext(
            flag_id="f1", challenge_slug="c1", artifact_dir=tmp_path
        )
        result = await run_validator_subprocess(
            _ArtifactProbe(), str(tmp_path), {}, ctx, timeout_s=10.0
        )
        assert result.correct is True

    async def test_malformed_envelope_raises_validator_error(self, context):
        # Direct hit on the runner — feed it broken JSON via subprocess
        # exec without going through ``run_validator_subprocess``.
        import asyncio
        import sys

        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-s",
            "-m",
            "app.services.validator_subprocess_runner",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate(b"not json")
        assert proc.returncode == 2
        import json as _json

        envelope = _json.loads(stdout)
        assert envelope["ok"] is False
        assert envelope["error"] == "envelope"
