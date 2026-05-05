"""Phase 9 — container profile registry."""

from __future__ import annotations

import dataclasses

import pytest

from app.services.orchestration import profiles


def test_registered_names_are_exact() -> None:
    assert profiles.names() == (
        "default-strict",
        "egress-proxied",
        "egress-proxied-sidecar",
        "llm-sandbox",
        "malware-sandbox",
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
    assert p.cap_add == ()
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


def test_no_profile_grants_caps() -> None:
    for name in profiles.names():
        p = profiles.get(name)
        assert p.cap_add == (), f"{name} grants caps"


def test_every_profile_has_no_new_privileges() -> None:
    for name in profiles.names():
        p = profiles.get(name)
        assert any(opt.startswith("no-new-privileges") for opt in p.security_opt), (
            f"profile {name} missing no-new-privileges"
        )
