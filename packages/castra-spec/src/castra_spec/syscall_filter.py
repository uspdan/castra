"""In-process seccomp-BPF filter that blocks network socket creation.

Used by the validator subprocess sandbox (audit finding R19). The
sandbox previously enforced CPU / memory / process budgets via
``resource.setrlimit`` but left the network wide open: a malicious or
compromised validator plugin could open an ``AF_INET`` socket and
exfiltrate whatever it could read, or use the API container as an SSRF
pivot into the backend network.

**Why seccomp and not a network namespace.** The obvious fix is
``unshare(CLONE_NEWUSER | CLONE_NEWNET)`` — an empty netns has no
route to anywhere. It works on the host but returns ``EPERM`` inside
the API container: Docker's default seccomp profile blocks ``unshare``
with ``CLONE_NEWUSER``. Allowing it would mean widening the API
container's own syscall surface to close a hole in a child process,
which trades a bigger boundary for a smaller one. ``prctl(PR_SET_SECCOMP)``
needs no privilege beyond ``PR_SET_NO_NEW_PRIVS``, is permitted by the
default profile, and denies the syscall outright rather than merely
making the network unreachable.

**What it blocks.** ``socket(2)`` for ``AF_INET``, ``AF_INET6`` and
``AF_PACKET``. ``AF_UNIX`` stays permitted because CPython's asyncio
event loop builds its self-pipe from a ``socketpair(2)``, and blocking
it would break the runner before the validator ever executes. There is
no unix socket mounted into the API container for a plugin to reach.

**Failure mode is closed.** The filter is irreversible once installed
(``NO_NEW_PRIVS`` guarantees a child cannot drop it), and the caller
treats an install failure as a refusal to run the validator unless the
operator has explicitly opted out via
``VALIDATOR_REQUIRE_NETWORK_ISOLATION=false``.
"""

from __future__ import annotations

import ctypes
import errno
import platform
import socket
from typing import Final, List, Tuple

# --- classic BPF opcodes (linux/bpf_common.h) ------------------------------
_BPF_LD_W_ABS: Final = 0x20  # BPF_LD | BPF_W | BPF_ABS
_BPF_JEQ_K: Final = 0x15  # BPF_JMP | BPF_JEQ | BPF_K
_BPF_RET_K: Final = 0x06  # BPF_RET | BPF_K

# --- seccomp return actions (linux/seccomp.h) ------------------------------
_SECCOMP_RET_ALLOW: Final = 0x7FFF0000
_SECCOMP_RET_ERRNO: Final = 0x00050000

# --- prctl options (linux/prctl.h) -----------------------------------------
_PR_SET_NO_NEW_PRIVS: Final = 38
_PR_SET_SECCOMP: Final = 22
_SECCOMP_MODE_FILTER: Final = 2

# --- struct seccomp_data field offsets -------------------------------------
# struct seccomp_data { int nr; __u32 arch; __u64 ip; __u64 args[6]; }
_OFFSET_NR: Final = 0
_OFFSET_ARCH: Final = 4
_OFFSET_ARG0: Final = 16

# AUDIT_ARCH_* token and __NR_socket, per architecture. The arch check is
# mandatory: without it, a process could switch to a compat ABI where the
# same syscall number means something else entirely.
_ARCH_TABLE: Final = {
    "x86_64": (0xC000003E, 41),
    "aarch64": (0xC00000B7, 198),
}

# Socket families the validator sandbox refuses. AF_PACKET (17) is not
# exposed by the ``socket`` module on every build, so it is spelled out.
_AF_PACKET: Final = 17
_DENIED_FAMILIES: Final = (int(socket.AF_INET), int(socket.AF_INET6), _AF_PACKET)


class SyscallFilterError(RuntimeError):
    """The seccomp filter could not be built or installed."""


class _SockFilter(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_uint16),
        ("jt", ctypes.c_uint8),
        ("jf", ctypes.c_uint8),
        ("k", ctypes.c_uint32),
    ]


class _SockFprog(ctypes.Structure):
    _fields_ = [
        ("len", ctypes.c_ushort),
        ("filter", ctypes.POINTER(_SockFilter)),
    ]


def is_supported() -> bool:
    """True when this architecture has a known syscall mapping."""

    return platform.machine() in _ARCH_TABLE


def build_program(
    machine: str, denied_errno: int = errno.EPERM
) -> List[Tuple[int, int, int, int]]:
    """Return the BPF program as ``(code, jt, jf, k)`` tuples.

    Split out from :func:`install` so the instruction sequence is unit
    testable without irreversibly filtering the test process.

    The program reads:

    1. ``arch`` — anything other than the expected ABI is denied
       outright rather than allowed, so a compat-mode syscall cannot
       slip past the number comparison below.
    2. ``nr`` — non-``socket`` syscalls are allowed through untouched.
       This filter is deliberately narrow; CPU, memory and process
       budgets remain the rlimits' job.
    3. ``args[0]`` — the address family. Denied families return
       ``denied_errno``; everything else (notably ``AF_UNIX``) passes.
    """

    try:
        arch_token, nr_socket = _ARCH_TABLE[machine]
    except KeyError as exc:
        raise SyscallFilterError(
            f"no seccomp syscall mapping for architecture {machine!r}; "
            "refusing to run a validator without network isolation"
        ) from exc

    deny = _SECCOMP_RET_ERRNO | (denied_errno & 0x0000FFFF)
    program: List[Tuple[int, int, int, int]] = [
        (_BPF_LD_W_ABS, 0, 0, _OFFSET_ARCH),
        (_BPF_JEQ_K, 1, 0, arch_token),  # expected arch → skip the deny
        (_BPF_RET_K, 0, 0, deny),
        (_BPF_LD_W_ABS, 0, 0, _OFFSET_NR),
        (_BPF_JEQ_K, 1, 0, nr_socket),  # socket() → inspect the family
        (_BPF_RET_K, 0, 0, _SECCOMP_RET_ALLOW),
        (_BPF_LD_W_ABS, 0, 0, _OFFSET_ARG0),
    ]

    # Each family jumps to the terminal deny. The jump target is counted
    # from the instruction *after* the jump, so a family at index i has
    # (remaining families) + 1 allow-instruction between it and the deny.
    count = len(_DENIED_FAMILIES)
    for index, family in enumerate(_DENIED_FAMILIES):
        program.append((_BPF_JEQ_K, count - index, 0, family))
    program.append((_BPF_RET_K, 0, 0, _SECCOMP_RET_ALLOW))
    program.append((_BPF_RET_K, 0, 0, deny))
    return program


def install() -> None:
    """Install the filter on the calling thread. Irreversible.

    Raises :class:`SyscallFilterError` if the architecture is unknown or
    either ``prctl`` call fails. Callers decide whether that is fatal.
    """

    program = build_program(platform.machine())
    instructions = (_SockFilter * len(program))(
        *[_SockFilter(*entry) for entry in program]
    )
    fprog = _SockFprog(len(program), instructions)

    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
    except OSError as exc:  # pragma: no cover — non-glibc host
        raise SyscallFilterError(f"could not load libc: {exc}") from exc

    # NO_NEW_PRIVS is a hard precondition: without it an unprivileged
    # process may not install a filter at all, and a setuid binary could
    # otherwise be used to shed it.
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        err = ctypes.get_errno()
        raise SyscallFilterError(
            f"prctl(PR_SET_NO_NEW_PRIVS) failed: {errno.errorcode.get(err, err)}"
        )

    if (
        libc.prctl(
            _PR_SET_SECCOMP, _SECCOMP_MODE_FILTER, ctypes.byref(fprog), 0, 0
        )
        != 0
    ):
        err = ctypes.get_errno()
        raise SyscallFilterError(
            f"prctl(PR_SET_SECCOMP) failed: {errno.errorcode.get(err, err)}"
        )


__all__ = [
    "SyscallFilterError",
    "build_program",
    "install",
    "is_supported",
]
