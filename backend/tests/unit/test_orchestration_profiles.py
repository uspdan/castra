"""Phase 9 — container profile registry."""

from __future__ import annotations

import dataclasses

import pytest

from app.services.orchestration import profiles


def test_registered_names_are_exact() -> None:
    # The ``suid-allowed`` profile was added so SUID-privesc and
    # related Linux-cap-dependent challenges can elevate inside the
    # container (the no-new-privileges bit had to be cleared and
    # the explicit caps granted). It is opt-in per-challenge.
    assert profiles.names() == (
        "default-strict",
        "egress-proxied",
        "egress-proxied-sidecar",
        "llm-sandbox",
        "malware-sandbox",
        "suid-allowed",
    )


def test_get_returns_frozen_dataclass() -> None:
    profile = profiles.get("default-strict")
    assert isinstance(profile, profiles.ContainerProfile)
    # frozen dataclasses raise on assignment
    with pytest.raises(dataclasses.FrozenInstanceError):
        profile.mem_limit = "1g"  # type: ignore[misc]


def test_unknown_profile_raises() -> None:
    with pytest.raises(profiles.UnknownProfile):
        profiles.get("does-not-exist")


def test_default_strict_minimums() -> None:
    p = profiles.get("default-strict")
    assert p.read_only is True
    assert "ALL" in p.cap_drop
    # default-strict allows the minimal cap set that lets
    # multi-process daemons (apache, nginx, sshd) drop privs at
    # start-up. Nothing here gives the process root on the host.
    assert p.cap_add == ("CHOWN", "SETGID", "SETUID", "SYS_CHROOT")
    assert p.network_mode == "bridge-isolated"
    assert p.egress_allowlist_required is False
    assert p.ttl_seconds_max <= 7_200


def test_malware_sandbox_is_stricter_than_default() -> None:
    base = profiles.get("default-strict")
    mal = profiles.get("malware-sandbox")
    assert mal.ttl_seconds_max < base.ttl_seconds_max
    assert mal.pids_limit < base.pids_limit
    assert mal.seccomp_profile == "malware-sandbox"


def test_egress_profile_requires_allowlist() -> None:
    p = profiles.get("egress-proxied")
    assert p.network_mode == "egress-proxied"
    assert p.egress_allowlist_required is True


def test_caps_are_bounded() -> None:
    """No profile may grant caps outside the documented allowlist —
    keep the surface tight even when individual profiles open it."""
    allowed = {"CHOWN", "SETGID", "SETUID", "SYS_CHROOT", "DAC_READ_SEARCH"}
    for name in profiles.names():
        p = profiles.get(name)
        for cap in p.cap_add:
            assert cap in allowed, f"{name} grants unexpected cap {cap}"


def test_no_new_privileges_is_default() -> None:
    """Every profile *except* ``suid-allowed`` keeps no-new-privileges
    on; the suid-allowed profile deliberately clears it so an inner
    SUID binary can elevate (documented use case)."""
    for name in profiles.names():
        p = profiles.get(name)
        if name == "suid-allowed":
            assert not any(
                opt.startswith("no-new-privileges") for opt in p.security_opt
            ), "suid-allowed must NOT set no-new-privileges"
            continue
        assert any(opt.startswith("no-new-privileges") for opt in p.security_opt), (
            f"profile {name} missing no-new-privileges"
        )
