"""Unit tests for the validator registry.

The discovery path is exercised end-to-end by the editable-install of
the backend in the host venv (requirements-test.txt declares ``-e .``,
which registers the three first-party entry points). These tests assert
the contract: discovery resolves the v1 trio, lookups succeed, and
duplicate registrations are refused.
"""

from __future__ import annotations

import pytest

from app.services.validator_registry import (
    DuplicateValidator,
    UnknownValidator,
    ValidatorRegistry,
    build_default_registry,
    discover_entry_points,
)
from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
)


class _Stub(Validator):
    name = "stub"

    async def validate(self, submission, config, context):  # pragma: no cover
        return ValidationResult(correct=False)


class TestRegistryBasics:
    def test_register_and_get(self):
        r = ValidatorRegistry()
        v = _Stub()
        r.register(v)
        assert r.get("stub") is v
        assert "stub" in r

    def test_duplicate_register_raises(self):
        r = ValidatorRegistry()
        r.register(_Stub())
        with pytest.raises(DuplicateValidator):
            r.register(_Stub())

    def test_get_unknown_raises(self):
        r = ValidatorRegistry()
        with pytest.raises(UnknownValidator):
            r.get("nope")

    def test_names_sorted(self):
        r = ValidatorRegistry()
        r.register(_Stub())

        class _Other(_Stub):
            name = "alpha"

        r.register(_Other())
        assert r.names() == ("alpha", "stub")


class TestEntryPointDiscovery:
    def test_default_registry_loads_v1_trio(self):
        r = build_default_registry()
        assert "exact" in r
        assert "regex" in r
        assert "multi_part" in r

    def test_discover_into_existing(self):
        r = ValidatorRegistry()
        discover_entry_points(r, select=["exact"])
        assert r.names() == ("exact",)

    def test_validator_load_yields_instance(self):
        r = build_default_registry()
        ex = r.get("exact")
        # Should be a constructed instance, not the class.
        assert not isinstance(ex, type)
        assert ex.name == "exact"
