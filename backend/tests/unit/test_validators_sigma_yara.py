"""Unit tests for the sigma + yara validators.

These tests exercise the validators directly (no subprocess sandbox)
so we can read coverage on the matchers and config error paths. The
end-to-end subprocess path is covered separately in
``test_validator_subprocess_sandbox.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.validators.sigma_rule import SigmaRuleValidator
from app.validators.yara_rule import YaraRuleValidator
from bluerange_spec import ValidationContext, ValidatorConfigError


# ---------------------------------------------------------------------------
# SigmaRuleValidator
# ---------------------------------------------------------------------------
def _events_fixture(tmp_path: Path, events: list[dict]) -> Path:
    path = tmp_path / "events.json"
    path.write_text(json.dumps(events))
    return path


def _sigma_context(tmp_path: Path) -> ValidationContext:
    return ValidationContext(
        flag_id="f1", challenge_slug="c1", artifact_dir=tmp_path
    )


_RULE_PWSH = """
title: PowerShell launched
status: experimental
logsource:
  product: windows
  category: process_creation
detection:
  selection:
    EventID: 4688
    Image|endswith: \\\\powershell.exe
  condition: selection
"""

_RULE_PWSH_NOT_SYSTEM = """
title: PowerShell launched by user
logsource:
  product: windows
  category: process_creation
detection:
  selection:
    Image|endswith: \\\\powershell.exe
  filter:
    User: SYSTEM
  condition: selection and not filter
"""


class TestSigmaRule:
    async def test_happy_path_match_set_equals_expected(self, tmp_path):
        v = SigmaRuleValidator()
        _events_fixture(
            tmp_path,
            [
                {"EventID": 4688, "Image": "C:\\Windows\\powershell.exe", "User": "alice"},
                {"EventID": 4688, "Image": "C:\\Windows\\REDACTED", "User": "alice"},
                {"EventID": 4624, "Image": None, "User": "alice"},
                {"EventID": 4688, "Image": "D:\\binaries\\powershell.exe", "User": "alice"},
                {"EventID": 4688, "Image": "powershell.exe", "User": "alice"},
            ],
        )
        config = {
            "events_filename": "events.json",
            "expected_match_indices": [0, 3],
        }
        result = await v.validate(_RULE_PWSH, config, _sigma_context(tmp_path))
        assert result.correct is True

    async def test_filter_excluded_via_not_clause(self, tmp_path):
        v = SigmaRuleValidator()
        _events_fixture(
            tmp_path,
            [
                {"Image": "C:\\powershell.exe", "User": "alice"},
                {"Image": "C:\\powershell.exe", "User": "SYSTEM"},
            ],
        )
        config = {
            "events_filename": "events.json",
            "expected_match_indices": [0],
        }
        result = await v.validate(
            _RULE_PWSH_NOT_SYSTEM, config, _sigma_context(tmp_path)
        )
        assert result.correct is True

    async def test_match_set_mismatch_returns_false(self, tmp_path):
        v = SigmaRuleValidator()
        _events_fixture(
            tmp_path,
            [
                {"EventID": 4688, "Image": "C:\\powershell.exe", "User": "alice"},
            ],
        )
        config = {
            "events_filename": "events.json",
            "expected_match_indices": [99],
        }
        result = await v.validate(_RULE_PWSH, config, _sigma_context(tmp_path))
        assert result.correct is False
        assert result.details["reason"] == "match_set_mismatch"

    async def test_invalid_yaml_rule(self, tmp_path):
        v = SigmaRuleValidator()
        _events_fixture(tmp_path, [{"x": 1}])
        config = {
            "events_filename": "events.json",
            "expected_match_indices": [],
        }
        result = await v.validate(":\nnot valid:", config, _sigma_context(tmp_path))
        assert result.correct is False
        assert result.details["reason"] in {"rule_parse_error", "no_condition"}

    async def test_required_logsource_mismatch(self, tmp_path):
        v = SigmaRuleValidator()
        _events_fixture(tmp_path, [{"x": 1}])
        config = {
            "events_filename": "events.json",
            "expected_match_indices": [],
            "require_logsource": {"product": "linux"},
        }
        result = await v.validate(_RULE_PWSH, config, _sigma_context(tmp_path))
        assert result.correct is False
        assert result.details["reason"] == "logsource_mismatch"

    async def test_path_traversal_rejected(self, tmp_path):
        v = SigmaRuleValidator()
        config = {
            "events_filename": "../etc/passwd",
            "expected_match_indices": [],
        }
        with pytest.raises(ValidatorConfigError):
            await v.validate(_RULE_PWSH, config, _sigma_context(tmp_path))

    async def test_missing_artifact_dir_raises(self):
        v = SigmaRuleValidator()
        ctx = ValidationContext(flag_id="f", challenge_slug="c")  # artifact_dir=None
        with pytest.raises(ValidatorConfigError):
            await v.validate(
                _RULE_PWSH,
                {"events_filename": "events.json", "expected_match_indices": []},
                ctx,
            )

    async def test_missing_fixture_file(self, tmp_path):
        v = SigmaRuleValidator()
        # No events.json on disk.
        config = {"events_filename": "events.json", "expected_match_indices": []}
        with pytest.raises(ValidatorConfigError):
            await v.validate(_RULE_PWSH, config, _sigma_context(tmp_path))

    async def test_oversized_rule_rejected(self, tmp_path):
        v = SigmaRuleValidator()
        _events_fixture(tmp_path, [])
        big = "title: x\n" + ("# pad\n" * 20000)
        config = {"events_filename": "events.json", "expected_match_indices": []}
        result = await v.validate(big, config, _sigma_context(tmp_path))
        assert result.correct is False
        assert result.details["reason"] == "oversized_rule"


# ---------------------------------------------------------------------------
# YaraRuleValidator
# ---------------------------------------------------------------------------
_YARA_RULE_HELLO = """
rule hello_world {
    strings:
        $a = "hello"
    condition:
        $a
}
"""


def _yara_fixtures(tmp_path: Path):
    samples = tmp_path / "samples"
    samples.mkdir()
    (samples / "evil.bin").write_bytes(b"hello world\n")
    (samples / "clean.bin").write_bytes(b"goodbye world\n")
    return tmp_path


def _yara_context(tmp_path: Path) -> ValidationContext:
    return ValidationContext(
        flag_id="f1", challenge_slug="c1", artifact_dir=tmp_path
    )


class TestYaraRule:
    async def test_happy_path(self, tmp_path):
        v = YaraRuleValidator()
        _yara_fixtures(tmp_path)
        config = {
            "samples_dir": "samples",
            "expected_matches": ["evil.bin"],
            "expected_no_match": ["clean.bin"],
        }
        result = await v.validate(_YARA_RULE_HELLO, config, _yara_context(tmp_path))
        assert result.correct is True

    async def test_rule_misses_positive(self, tmp_path):
        v = YaraRuleValidator()
        _yara_fixtures(tmp_path)
        rule = """rule never { strings: $a = "zzzz_not_present" condition: $a }"""
        config = {
            "samples_dir": "samples",
            "expected_matches": ["evil.bin"],
        }
        result = await v.validate(rule, config, _yara_context(tmp_path))
        assert result.correct is False
        assert result.details["reason"] == "expected_match_no_match"

    async def test_rule_overmatches_negative(self, tmp_path):
        v = YaraRuleValidator()
        _yara_fixtures(tmp_path)
        rule = """rule too_broad { strings: $a = "world" condition: $a }"""
        config = {
            "samples_dir": "samples",
            "expected_matches": ["evil.bin"],
            "expected_no_match": ["clean.bin"],
        }
        result = await v.validate(rule, config, _yara_context(tmp_path))
        assert result.correct is False
        assert result.details["reason"] == "expected_no_match_matched"

    async def test_invalid_yara_syntax(self, tmp_path):
        v = YaraRuleValidator()
        _yara_fixtures(tmp_path)
        config = {
            "samples_dir": "samples",
            "expected_matches": ["evil.bin"],
        }
        result = await v.validate("not a yara rule", config, _yara_context(tmp_path))
        assert result.correct is False
        assert result.details["reason"] == "rule_compile_error"

    async def test_path_traversal_rejected(self, tmp_path):
        v = YaraRuleValidator()
        _yara_fixtures(tmp_path)
        config = {
            "samples_dir": "samples",
            "expected_matches": ["../etc/passwd"],
        }
        with pytest.raises(ValidatorConfigError):
            await v.validate(_YARA_RULE_HELLO, config, _yara_context(tmp_path))

    async def test_oversized_sample_rejected(self, tmp_path):
        v = YaraRuleValidator()
        _yara_fixtures(tmp_path)
        big = tmp_path / "samples" / "big.bin"
        big.write_bytes(b"x" * 1024 * 1024)
        config = {
            "samples_dir": "samples",
            "expected_matches": ["big.bin"],
            "max_sample_bytes": 1024,
        }
        result = await v.validate(_YARA_RULE_HELLO, config, _yara_context(tmp_path))
        assert result.correct is False
        assert result.details["reason"] == "fixture_oversize"

    async def test_missing_artifact_dir_raises(self):
        v = YaraRuleValidator()
        ctx = ValidationContext(flag_id="f", challenge_slug="c")
        with pytest.raises(ValidatorConfigError):
            await v.validate(
                _YARA_RULE_HELLO,
                {"samples_dir": "samples", "expected_matches": ["x.bin"]},
                ctx,
            )

    async def test_missing_fixture_file(self, tmp_path):
        v = YaraRuleValidator()
        _yara_fixtures(tmp_path)
        config = {
            "samples_dir": "samples",
            "expected_matches": ["does-not-exist.bin"],
        }
        result = await v.validate(_YARA_RULE_HELLO, config, _yara_context(tmp_path))
        assert result.correct is False
        assert result.details["reason"] == "fixture_missing"
