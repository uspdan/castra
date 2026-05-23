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


# --- escape-attempt probes (R19 audit finding) --------------------------
# Each of these tries to do something the sandbox should refuse. The
# tests assert the failure mode — either a ValidatorError (child died
# under a rlimit kill) or a ValidatorTimeoutError. Probes that the
# current rlimit-only sandbox doesn't block are flagged xfail with a
# strict=False so the matrix is self-documenting.


class _MemoryBurst(Validator):
    """Try to allocate ~1 GiB. The 512 MiB RLIMIT_AS ceiling should
    kill the child with MemoryError → ValidatorError."""

    name = "_memory_burst"
    requires_subprocess = True
    default_timeout_s = 10.0

    async def validate(self, submission, config, context):
        # Allocate a contiguous bytearray well over the 512 MiB cap.
        _ = bytearray(1_073_741_824)  # 1 GiB
        return ValidationResult(correct=True)


class _CpuBurn(Validator):
    """Busy-loop past the wall-clock budget. The parent
    ``asyncio.timeout`` raises ValidatorTimeoutError; RLIMIT_CPU
    backs it up with SIGXCPU."""

    name = "_cpu_burn"
    requires_subprocess = True
    default_timeout_s = 0.3

    async def validate(self, submission, config, context):
        end_after_s = 30
        import time

        start = time.monotonic()
        x = 0
        while time.monotonic() - start < end_after_s:
            x = (x + 1) % 2**31
        return ValidationResult(correct=True)


class _StdoutFlood(Validator):
    """Write past RLIMIT_FSIZE (16 MiB cap on stdout writes). The
    kernel sends SIGXFSZ; the child dies and the parent surfaces a
    ValidatorError."""

    name = "_stdout_flood"
    requires_subprocess = True
    default_timeout_s = 10.0

    async def validate(self, submission, config, context):
        import sys

        chunk = "A" * (1024 * 1024)
        # 32 MiB > RLIMIT_FSIZE cap.
        for _ in range(32):
            sys.stdout.write(chunk)
        return ValidationResult(correct=True)


class _ForkBomb(Validator):
    """Try to spawn more processes than RLIMIT_NPROC permits. The
    fork() call raises BlockingIOError → ValidatorError."""

    name = "_fork_bomb"
    requires_subprocess = True
    default_timeout_s = 10.0

    async def validate(self, submission, config, context):
        import multiprocessing

        children = []
        try:
            # Try to start more children than the 32-NPROC ceiling.
            for _ in range(64):
                p = multiprocessing.Process(
                    target=lambda: None
                )
                p.start()
                children.append(p)
        finally:
            for p in children:
                try:
                    p.join(timeout=0.1)
                except Exception:
                    pass
        return ValidationResult(correct=True)


class _SocketOpenIPv4(Validator):
    """Try to open an outbound IPv4 connection. The current
    rlimit-only sandbox does NOT block this — documents the gap
    (tracked as a future seccomp / netns sprint)."""

    name = "_socket_open_v4"
    requires_subprocess = True
    default_timeout_s = 5.0

    async def validate(self, submission, config, context):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Don't actually connect — just construct the socket. If
            # the sandbox blocks AF_INET creation, ``socket()`` raises
            # PermissionError; if it doesn't, we close cleanly.
            s.close()
            return ValidationResult(correct=True)
        finally:
            s.close()


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

    # -------------------------------------------------------------------
    # R19 escape-attempt coverage. Documents what the rlimit-only
    # sandbox actually blocks. Anything that currently *doesn't* block
    # is marked xfail (strict=False) so the matrix is honest about
    # residual surface — the audit register tracks the seccomp work
    # that would close the gaps.
    # -------------------------------------------------------------------
    async def test_blocks_memory_burst(self, context):
        v = _MemoryBurst()
        with pytest.raises(ValidatorError):
            # RLIMIT_AS (512 MiB) kills the child when bytearray
            # tries to reserve 1 GiB. Surfaces as ValidatorError
            # rather than MemoryError because the runner can't
            # serialise the partial state back.
            await run_validator_subprocess(
                v, "x", {}, context, timeout_s=10.0
            )

    async def test_blocks_cpu_burn(self, context):
        v = _CpuBurn()
        # The parent's asyncio.timeout fires first under normal
        # conditions; RLIMIT_CPU is the kernel backstop and would
        # raise ValidatorError on a slow runner. Accept either.
        with pytest.raises((ValidatorTimeoutError, ValidatorError)):
            await run_validator_subprocess(
                v, "x", {}, context, timeout_s=0.5
            )

    async def test_blocks_stdout_flood(self, context):
        v = _StdoutFlood()
        # The runner writes its JSON result to stdout; RLIMIT_FSIZE
        # caps total writes. The flood exhausts the cap before the
        # runner can emit its envelope, so the parent sees a dead
        # child and raises ValidatorError. (On platforms where
        # asyncio buffers more aggressively, the parent may see a
        # truncated envelope and raise ValidatorError via the
        # malformed-envelope branch.)
        with pytest.raises(ValidatorError):
            await run_validator_subprocess(
                v, "x", {}, context, timeout_s=10.0
            )

    @pytest.mark.xfail(
        reason=(
            "Current sandbox is rlimit-only; AF_INET socket creation "
            "is permitted. Closing this gap requires seccomp or a "
            "network namespace, tracked in the audit register."
        ),
        strict=False,
    )
    async def test_blocks_outbound_socket(self, context):
        v = _SocketOpenIPv4()
        # No exception expected today (the rlimit sandbox doesn't
        # block this). The xfail keeps the matrix honest: when the
        # seccomp profile lands and starts blocking AF_INET, this
        # test will start raising and we'll flip it to strict=True.
        with pytest.raises(ValidatorError):
            await run_validator_subprocess(
                v, "x", {}, context, timeout_s=5.0
            )

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
