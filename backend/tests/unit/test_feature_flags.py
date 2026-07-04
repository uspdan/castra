"""Unit tests for the feature-flag registry (CLAUDE.md §19).

Covers: registry defaults, on/off overrides, whitespace tolerance,
malformed-token skipping, and the fail-closed guarantee for unknown
flags and empty config.
"""

from __future__ import annotations

import types

import pytest

from app.services import feature_flags
from app.services.feature_flags import all_flags, is_enabled, registered_flags


@pytest.fixture
def set_flags(monkeypatch):
    def _set(raw: str) -> None:
        monkeypatch.setattr(
            feature_flags,
            "get_settings",
            lambda: types.SimpleNamespace(FEATURE_FLAGS=raw),
        )

    return _set


def test_unknown_flag_fails_closed(set_flags) -> None:
    set_flags("FEATURE_DOES_NOT_EXIST=on")
    assert is_enabled("FEATURE_DOES_NOT_EXIST") is False


def test_registered_flag_defaults_off(set_flags) -> None:
    set_flags("")
    # Every shipped flag defaults OFF (ship dark).
    for name in registered_flags():
        assert is_enabled(name) is False


def test_override_turns_flag_on(set_flags) -> None:
    set_flags("FEATURE_API_V1_WRITEUPS=on")
    assert is_enabled("FEATURE_API_V1_WRITEUPS") is True
    # Sibling flag unaffected.
    assert is_enabled("FEATURE_API_V1_COMPETITIONS") is False


def test_override_off_is_explicit(set_flags) -> None:
    set_flags("FEATURE_API_V1_WRITEUPS=off")
    assert is_enabled("FEATURE_API_V1_WRITEUPS") is False


@pytest.mark.parametrize("token", ["on", "true", "1", "enabled", "yes", "ON", "True"])
def test_truthy_tokens(set_flags, token) -> None:
    set_flags(f"FEATURE_API_V1_WRITEUPS={token}")
    assert is_enabled("FEATURE_API_V1_WRITEUPS") is True


def test_whitespace_and_multiple_pairs(set_flags) -> None:
    set_flags("  FEATURE_API_V1_WRITEUPS = on ,  FEATURE_API_V1_COMPETITIONS=on ")
    assert is_enabled("FEATURE_API_V1_WRITEUPS") is True
    assert is_enabled("FEATURE_API_V1_COMPETITIONS") is True


def test_malformed_tokens_skipped_use_default(set_flags) -> None:
    # No '=', and an unrecognised value — both ignored, flag stays default.
    set_flags("garbage, FEATURE_API_V1_WRITEUPS=maybe")
    assert is_enabled("FEATURE_API_V1_WRITEUPS") is False


def test_empty_config_all_default(set_flags) -> None:
    set_flags("")
    resolved = all_flags()
    assert set(resolved) == set(registered_flags())
    assert all(v is False for v in resolved.values())
