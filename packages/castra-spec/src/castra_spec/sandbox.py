"""Sandboxing primitives for validator dispatch.

Three concerns live here:

1. **Time budget.** Every validator call is wrapped in
   ``asyncio.timeout(validator.default_timeout_s)``. A buggy or
   adversarial regex / parser cannot hang the request loop.

2. **Read-only artefact exposure.** When a validator declares it
   needs access to challenge artefacts, the platform copies the
   canonical directory into a per-submission temp tree and chmods
   every entry to ``0555`` (dirs) / ``0444`` (files). The validator
   receives the *copy* in its :class:`ValidationContext`; the
   canonical directory is never exposed.

3. **Subprocess sandbox.** Validators that declare
   ``requires_subprocess=True`` (Phase 10's yara/sigma) run inside a
   forked Python child with ``resource.setrlimit`` enforcing CPU,
   address-space, NPROC and file-size budgets, plus a JSON-stdio
   protocol so a compromised child cannot escape into the parent's
   process state.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Mapping, Optional

from .validators import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
    ValidatorError,
    ValidatorTimeoutError,
)


# Per-call resource ceilings for the subprocess sandbox. CPU is the
# inner ceiling — it is wall-clock-agnostic but covers the
# pathological "tight loop" case the parent's wait_for can still
# observe via SIGXCPU. Memory is set generously enough for a YARA
# rule scanning ~MB of artefacts and a Sigma rule walking a JSON log;
# tighten via per-validator overrides in the future if a plugin
# needs less.
_DEFAULT_RLIMIT_AS_BYTES = 512 * 1024 * 1024  # 512 MiB
_DEFAULT_RLIMIT_NPROC = 32
_DEFAULT_RLIMIT_FSIZE = 16 * 1024 * 1024  # 16 MiB stdout cap
_DEFAULT_RLIMIT_NOFILE = 128
# Buffer over the wall-clock budget so wait_for fires first under
# normal conditions; CPU is the last-resort kernel kill.
_CPU_BUFFER_S = 2.0


_DIR_MODE = 0o555
_FILE_MODE = 0o444


async def run_validator(
    validator: Validator,
    submission: str,
    config: Mapping[str, Any],
    context: ValidationContext,
    *,
    timeout_s: Optional[float] = None,
) -> ValidationResult:
    """Dispatch a validator with the platform's time-budget guard.

    ``timeout_s`` overrides the validator's
    :attr:`Validator.default_timeout_s`. The override exists because
    the platform's flag-submission path may apply a tighter budget
    than the plugin author advertises (defence in depth) — never a
    looser one.
    """

    budget = timeout_s if timeout_s is not None else validator.default_timeout_s
    if validator.requires_subprocess:
        return await run_validator_subprocess(
            validator, submission, config, context, timeout_s=budget
        )
    try:
        # asyncio.wait_for is used in place of asyncio.timeout because
        # the host venv runs Python 3.10 (asyncio.timeout is 3.11+).
        # The runtime image is 3.12 — we deliberately keep one
        # codepath rather than version-gating the sandbox primitive.
        return await asyncio.wait_for(
            validator.validate(submission, config, context),
            timeout=budget,
        )
    except asyncio.TimeoutError as exc:
        raise ValidatorTimeoutError(
            f"validator {validator.name!r} exceeded {budget:.2f}s budget"
        ) from exc


async def run_validator_subprocess(
    validator: Validator,
    submission: str,
    config: Mapping[str, Any],
    context: ValidationContext,
    *,
    timeout_s: float,
) -> ValidationResult:
    """Run a ``requires_subprocess=True`` validator under rlimits.

    Spawns ``python -m castra_spec.subprocess_runner`` with
    a tight inherited environment, sends a JSON envelope on stdin, and
    parses the JSON envelope on stdout. The child applies the rlimits
    *itself* via :mod:`resource` — passing them through the envelope
    rather than having the parent set them with ``preexec_fn`` keeps
    the call thread-safe (preexec_fn requires fork-only spawn).

    Wall-clock timeout is enforced in the parent via
    :func:`asyncio.wait_for`. CPU + memory limits are inner backstops
    set generously enough to absorb pysigma / yara-python's working
    set. Both fire as :class:`ValidatorTimeoutError` from the parent's
    perspective so callers don't need to discriminate the cause.
    """

    if sys.platform == "win32":  # pragma: no cover — Linux-only deployment
        raise ValidatorError(
            "subprocess sandbox requires a POSIX host (resource.setrlimit "
            "is unavailable on win32)"
        )

    envelope: dict[str, Any] = {
        "validator_module": validator.__class__.__module__,
        "validator_class": validator.__class__.__name__,
        "submission": submission,
        "config": dict(config),
        "context": _context_to_primitive(context),
        "rlimits": _build_rlimits(timeout_s),
        # R19 — the child installs a seccomp filter denying inet
        # sockets before it imports the validator module. Default-on;
        # the operator can only disable it by explicit config, and the
        # child then reports the degraded posture rather than silently
        # running with the network open.
        "require_network_isolation": _require_network_isolation(),
    }
    payload = json.dumps(envelope).encode("utf-8")

    # The child reads from stdin, writes to stdout. We forward stderr
    # to the parent's stderr so plugin authors see tracebacks during
    # development. Production deployments redirect stderr to the
    # platform's structured logger.
    # We pass an explicit, minimal env (see ``_subprocess_env``) so
    # there is no PYTHONHOME / PYTHONSTARTUP to hijack the child. We
    # deliberately do NOT use ``-E`` / ``-I`` here: those flags would
    # also discard the PYTHONPATH we just placed in the env, which is
    # how the test venv exposes the in-repo packages. ``-s`` keeps
    # user site-packages off sys.path.
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-s",  # don't add user-site to sys.path
        "-m",
        "castra_spec.subprocess_runner",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_subprocess_env(),
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(payload), timeout=timeout_s
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        try:
            await asyncio.wait_for(proc.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass
        raise ValidatorTimeoutError(
            f"validator {validator.name!r} subprocess exceeded "
            f"{timeout_s:.2f}s budget"
        ) from exc

    if proc.returncode and proc.returncode < 0:
        # Negative returncode = killed by signal (e.g. SIGKILL/SIGXCPU
        # from rlimit). Treat as a timeout from the caller's
        # perspective — the validator did not complete within budget.
        raise ValidatorTimeoutError(
            f"validator {validator.name!r} subprocess killed by signal "
            f"{-proc.returncode} (rlimit or external SIGKILL)"
        )

    if not stdout:
        raise ValidatorError(
            f"validator {validator.name!r} subprocess produced no output "
            f"(stderr: {stderr.decode('utf-8', errors='replace')[:200]!r})"
        )

    try:
        response = json.loads(stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidatorError(
            f"validator {validator.name!r} subprocess returned malformed "
            f"JSON: {exc}"
        ) from exc

    if response.get("ok"):
        result_data = response.get("result") or {}
        return ValidationResult(
            correct=bool(result_data.get("correct", False)),
            partial=bool(result_data.get("partial", False)),
            details=dict(result_data.get("details") or {}),
        )

    error_kind = response.get("error", "validator")
    message = str(response.get("message", "unknown subprocess error"))
    if error_kind == "config":
        raise ValidatorConfigError(message)
    if error_kind == "sandbox":
        # The child refused to run because it could not isolate itself.
        # Surface it as-is rather than as a validator fault — this is
        # an operator/platform condition, not a bad rule.
        raise ValidatorError(
            f"validator {validator.name!r} not run: {message}"
        )
    raise ValidatorError(
        f"validator {validator.name!r} failed: {message} "
        f"(kind={error_kind})"
    )


def _context_to_primitive(context: ValidationContext) -> dict[str, Any]:
    return {
        "flag_id": context.flag_id,
        "challenge_slug": context.challenge_slug,
        "artifact_dir": str(context.artifact_dir) if context.artifact_dir else None,
        "submission_metadata": dict(context.submission_metadata or {}),
    }


def _build_rlimits(timeout_s: float) -> dict[str, int]:
    # CPU rlimit is integer seconds; round up so a fractional wall
    # clock budget still leaves CPU headroom. The wall-clock guard in
    # the parent fires first under normal conditions.
    cpu_seconds = max(1, int(timeout_s + _CPU_BUFFER_S) + 1)
    return {
        "RLIMIT_CPU": cpu_seconds,
        "RLIMIT_AS": _DEFAULT_RLIMIT_AS_BYTES,
        "RLIMIT_NPROC": _DEFAULT_RLIMIT_NPROC,
        "RLIMIT_FSIZE": _DEFAULT_RLIMIT_FSIZE,
        "RLIMIT_NOFILE": _DEFAULT_RLIMIT_NOFILE,
    }


# Host-application hook for the isolation policy. The platform sets
# this at import time to read its Settings; standalone SDK users get
# the environment-variable default below. A hook rather than a config
# import keeps the SDK free of any dependency on the host app — the
# whole point of the extraction — while preserving the platform's
# ability to make this an operator setting.
require_network_isolation_hook: Optional[Callable[[], bool]] = None


def _require_network_isolation() -> bool:
    """Whether the child must refuse to run without its seccomp filter.

    Resolution order: host hook (the platform wires its Settings in),
    else the ``CASTRA_SANDBOX_REQUIRE_ISOLATION`` env var, else True.
    Fail-closed on any error — a broken hook must not open the sandbox.
    """

    try:
        if require_network_isolation_hook is not None:
            return bool(require_network_isolation_hook())
        raw = os.environ.get("CASTRA_SANDBOX_REQUIRE_ISOLATION", "true")
        return raw.strip().lower() not in ("0", "false", "no", "off")
    except Exception:  # noqa: BLE001 — hook problems must not open the sandbox
        return True


def _subprocess_env() -> dict[str, str]:
    """Build a minimal environment for the validator child.

    Drops every secret / connection-string we know about; preserves
    the bits Python itself needs (PATH, LANG, etc.) so ``importlib``
    can resolve site-packages. The child also re-scrubs at startup as
    defence-in-depth.
    """

    keep = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "PYTHONPATH", "HOME"}
    env: dict[str, str] = {}
    for key in keep:
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    return env


@asynccontextmanager
async def readonly_artifact_dir(source: Path) -> AsyncIterator[Path]:
    """Yield a read-only copy of ``source`` for a single validator call.

    Implementation: copy the tree into a fresh tempdir; chmod every
    entry to ``0555`` / ``0444``; yield the tempdir path; cleanup on
    exit. The caller is responsible for honouring ``ValidationContext.
    artifact_dir = None`` when artefacts aren't needed — most v1
    flags don't read artefacts.
    """

    tmp_root = Path(tempfile.mkdtemp(prefix="castra-artefact-"))
    try:
        await asyncio.to_thread(_copy_readonly, source, tmp_root)
        yield tmp_root
    finally:
        await asyncio.to_thread(_force_remove_tree, tmp_root)


def _copy_readonly(source: Path, dest: Path) -> None:
    if not source.exists():
        return
    if source.is_file():
        shutil.copy2(source, dest / source.name)
        os.chmod(dest / source.name, _FILE_MODE)
        os.chmod(dest, _DIR_MODE)
        return
    # ``copytree`` requires the destination not to exist; we created
    # ``dest`` ourselves via mkdtemp. Copy *into* it.
    for item in source.iterdir():
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    _chmod_tree(dest)


def _chmod_tree(root: Path) -> None:
    for dirpath, dirnames, filenames in os.walk(root):
        for fname in filenames:
            os.chmod(os.path.join(dirpath, fname), _FILE_MODE)
        for dname in dirnames:
            os.chmod(os.path.join(dirpath, dname), _DIR_MODE)
    os.chmod(root, _DIR_MODE)


def _force_remove_tree(path: Path) -> None:
    # The tree is ``0555``/``0444``. Unlinking a file requires write
    # on the *parent directory*, not on the file itself, so we walk
    # the tree and chmod every directory back to ``0700`` before
    # rmtree runs. We also chmod files to ``0600`` so any onerror
    # branch (e.g. file held by another process) can succeed.
    if not path.exists():
        return
    for dirpath, dirnames, filenames in os.walk(path, topdown=True):
        os.chmod(dirpath, 0o700)
        for fname in filenames:
            try:
                os.chmod(os.path.join(dirpath, fname), 0o600)
            except OSError:
                pass
    shutil.rmtree(path)


__all__ = [
    "readonly_artifact_dir",
    "run_validator",
    "run_validator_subprocess",
]
