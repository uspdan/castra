"""Phase 9 — bundled seccomp profile loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.security import seccomp


def test_default_strict_parses() -> None:
    profile = seccomp.load_profile("default-strict")
    assert profile["defaultAction"] == "SCMP_ACT_ALLOW"
    assert isinstance(profile["syscalls"], list)
    assert any("unshare" in entry.get("names", []) for entry in profile["syscalls"])


def test_malware_sandbox_parses_and_is_stricter() -> None:
    profile = seccomp.load_profile("malware-sandbox")
    flat: list[str] = [n for entry in profile["syscalls"] for n in entry.get("names", [])]
    # Network syscalls denied in malware-sandbox but not in default-strict.
    assert "socket" in flat
    assert "ptrace" in flat


def test_validate_all_profiles_succeeds() -> None:
    out = seccomp.validate_all_profiles()
    assert "default-strict" in out
    assert "malware-sandbox" in out
    for sha in out.values():
        assert len(sha) == 64
        int(sha, 16)  # raises if not hex


def test_tampered_profile_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed JSON file in the seccomp dir fails the validator."""
    fake_dir = tmp_path
    (fake_dir / "default-strict.json").write_text("{ this is not json")
    monkeypatch.setattr(seccomp, "_HERE", fake_dir)

    with pytest.raises(seccomp.SeccompProfileError):
        seccomp.load_profile("default-strict")


def test_missing_required_key_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_dir = tmp_path
    (fake_dir / "x.json").write_text(json.dumps({"defaultAction": "SCMP_ACT_ALLOW"}))
    monkeypatch.setattr(seccomp, "_HERE", fake_dir)

    with pytest.raises(seccomp.SeccompProfileError, match="syscalls"):
        seccomp.load_profile("x")
