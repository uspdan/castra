"""Seccomp-BPF filter used by the validator sandbox (audit finding R19).

The filter itself is exercised end-to-end in
``test_validator_subprocess_sandbox.py`` (a real child process really
does fail to open a socket). What that cannot check is the *shape* of
the BPF program on architectures the test host isn't running, or the
jump arithmetic — the classic way to get a seccomp filter wrong is an
off-by-one in a jump offset, which silently turns a deny into an allow.

So this module runs the program through a small interpreter for the
three opcodes the filter uses, and asserts the verdict for every
(arch, syscall, family) combination that matters. A miscounted jump
shows up here as an ALLOW where a deny was intended.
"""

from __future__ import annotations

import errno
import socket
import struct

import pytest

from app.security.syscall_filter import (
    SyscallFilterError,
    build_program,
    is_supported,
)


_BPF_LD_W_ABS = 0x20
_BPF_JEQ_K = 0x15
_BPF_RET_K = 0x06

_SECCOMP_RET_ALLOW = 0x7FFF0000
_SECCOMP_RET_ERRNO = 0x00050000

_ARCH_X86_64 = 0xC000003E
_ARCH_AARCH64 = 0xC00000B7
_NR_SOCKET = {"x86_64": 41, "aarch64": 198}

_AF_PACKET = 17


def _seccomp_data(nr: int, arch: int, arg0: int = 0) -> bytes:
    """Pack a ``struct seccomp_data`` the filter can be run against."""

    return struct.pack(
        "<iIQ6Q", nr, arch, 0, arg0, 0, 0, 0, 0, 0
    )


def _run(program, data: bytes) -> int:
    """Interpret the BPF program; return the seccomp action.

    Supports only BPF_LD|W|ABS, BPF_JMP|JEQ|K and BPF_RET|K — the three
    opcodes ``build_program`` emits. Anything else is a test failure,
    because it means the filter grew an instruction this interpreter
    (and therefore this test) no longer validates.
    """

    acc = 0
    pc = 0
    steps = 0
    while True:
        steps += 1
        assert steps < 1000, "BPF program did not terminate"
        code, jt, jf, k = program[pc]
        if code == _BPF_LD_W_ABS:
            (acc,) = struct.unpack_from("<I", data, k)
            pc += 1
        elif code == _BPF_JEQ_K:
            pc += 1 + (jt if acc == k else jf)
        elif code == _BPF_RET_K:
            return k
        else:  # pragma: no cover — guard against silent opcode drift
            pytest.fail(f"unhandled BPF opcode {code:#x} at pc={pc}")


_DENY = _SECCOMP_RET_ERRNO | errno.EPERM


class TestProgramShape:
    def test_unknown_architecture_is_refused(self):
        # Fail-closed: no syscall mapping means no filter, and the
        # caller must not fall back to running unsandboxed.
        with pytest.raises(SyscallFilterError):
            build_program("s390x")

    def test_is_supported_matches_the_table(self):
        assert is_supported() in (True, False)
        assert build_program("x86_64")
        assert build_program("aarch64")

    def test_program_is_all_known_opcodes(self):
        for code, _, _, _ in build_program("x86_64"):
            assert code in (_BPF_LD_W_ABS, _BPF_JEQ_K, _BPF_RET_K)


class TestVerdicts:
    @pytest.fixture(params=["x86_64", "aarch64"])
    def arch(self, request):
        return request.param

    @pytest.fixture
    def program(self, arch):
        return build_program(arch)

    @pytest.fixture
    def arch_token(self, arch):
        return _ARCH_X86_64 if arch == "x86_64" else _ARCH_AARCH64

    @pytest.mark.parametrize(
        "family",
        [socket.AF_INET, socket.AF_INET6, _AF_PACKET],
        ids=["AF_INET", "AF_INET6", "AF_PACKET"],
    )
    def test_denies_network_families(
        self, program, arch, arch_token, family
    ):
        verdict = _run(
            program,
            _seccomp_data(_NR_SOCKET[arch], arch_token, int(family)),
        )
        assert verdict == _DENY, (
            f"socket(family={int(family)}) must be denied — a jump "
            "offset is likely off by one"
        )

    @pytest.mark.parametrize(
        "family",
        [socket.AF_UNIX, 40],  # AF_UNIX, AF_VSOCK
        ids=["AF_UNIX", "AF_VSOCK"],
    )
    def test_allows_non_network_families(
        self, program, arch, arch_token, family
    ):
        verdict = _run(
            program,
            _seccomp_data(_NR_SOCKET[arch], arch_token, int(family)),
        )
        assert verdict == _SECCOMP_RET_ALLOW

    def test_allows_unrelated_syscalls(self, program, arch, arch_token):
        # read(2) on x86_64 is 0, on aarch64 63. Neither is socket();
        # the filter must not touch them or the child cannot run at all.
        for nr in (0, 63, 1, 12, 257):
            if nr == _NR_SOCKET[arch]:
                continue
            verdict = _run(program, _seccomp_data(nr, arch_token))
            assert verdict == _SECCOMP_RET_ALLOW, f"syscall {nr} blocked"

    def test_denies_foreign_architecture(self, program, arch_token):
        # A compat-ABI syscall carries a different arch token; syscall
        # numbers there mean different things, so the filter must deny
        # rather than fall through to the number comparison.
        foreign = 0x40000003  # AUDIT_ARCH_I386
        assert foreign != arch_token
        verdict = _run(program, _seccomp_data(41, foreign, socket.AF_UNIX))
        assert verdict == _DENY

    def test_denied_errno_is_configurable(self, arch, arch_token):
        program = build_program(arch, denied_errno=errno.EACCES)
        verdict = _run(
            program,
            _seccomp_data(_NR_SOCKET[arch], arch_token, socket.AF_INET),
        )
        assert verdict == _SECCOMP_RET_ERRNO | errno.EACCES


class TestFailClosedWiring:
    """The runner must refuse to proceed when the filter won't install."""

    def _isolate(self, monkeypatch, required, raises):
        from app.services import validator_subprocess_runner as runner
        from app.security import syscall_filter

        def fake_install():
            if raises:
                raise SyscallFilterError("kernel said no")

        monkeypatch.setattr(syscall_filter, "install", fake_install)
        return runner._isolate_network(required)

    def test_install_failure_when_required_returns_sandbox_error(
        self, monkeypatch
    ):
        result = self._isolate(monkeypatch, required=True, raises=True)
        assert result is not None
        assert result["ok"] is False
        assert result["error"] == "sandbox"
        assert "network isolation" in result["message"]

    def test_install_failure_when_opted_out_proceeds(self, monkeypatch):
        assert self._isolate(monkeypatch, required=False, raises=True) is None

    def test_successful_install_proceeds(self, monkeypatch):
        assert self._isolate(monkeypatch, required=True, raises=False) is None


class TestParentDefaults:
    def test_isolation_is_on_by_default(self):
        from app.services.validator_sandbox import _require_network_isolation

        assert _require_network_isolation() is True

    def test_isolation_fails_closed_when_config_unavailable(
        self, monkeypatch
    ):
        # A broken/missing config must not be a route to an open sandbox.
        import app.config as config_module
        from app.services.validator_sandbox import _require_network_isolation

        def boom():
            raise RuntimeError("config exploded")

        monkeypatch.setattr(config_module, "get_settings", boom)
        assert _require_network_isolation() is True
