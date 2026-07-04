"""Unit tests for the rule-based incident-report analysis validator."""

from __future__ import annotations

import pytest
from bluerange_spec import ValidationContext, ValidatorConfigError

from app.validators.report_analysis import ReportAnalysisValidator

CTX = ValidationContext(flag_id="f1", challenge_slug="c1")

_RUBRIC = {
    "must_mention_iocs": ["192.0.2.10", "evil.example"],
    "must_cite_techniques": ["T1059", "T1071.001"],
    "sections_required": ["summary", "timeline", "iocs", "containment"],
}

_GOOD_REPORT = """
# Summary
The host beaconed to evil.example over the C2 channel.

## Timeline
09:00 initial access, 09:05 execution via T1059 (PowerShell).
Exfiltration used T1071.001 web protocols to 192.0.2.10.

## IOCs
- 192.0.2.10
- evil.example

## Containment
Isolated the host, rotated credentials.
"""


async def test_complete_report_passes() -> None:
    res = await ReportAnalysisValidator().validate(_GOOD_REPORT, _RUBRIC, CTX)
    assert res.correct is True
    assert res.details["score"] == 1.0
    assert res.details["missing_iocs"] == []
    assert res.details["missing_techniques"] == []
    assert res.details["missing_sections"] == []


async def test_missing_ioc_and_technique_fail_with_breakdown() -> None:
    report = """
    # Summary
    Something happened. Timeline and IOCs and Containment noted.
    Used T1059.
    """
    res = await ReportAnalysisValidator().validate(report, _RUBRIC, CTX)
    assert res.correct is False
    assert "192.0.2.10" in res.details["missing_iocs"]
    assert "evil.example" in res.details["missing_iocs"]
    assert "T1071.001" in res.details["missing_techniques"]
    assert 0.0 < res.details["score"] < 1.0


async def test_technique_id_whole_token_match() -> None:
    # "T1059" must not be satisfied by "T10591".
    cfg = {"must_cite_techniques": ["T1059"]}
    near = await ReportAnalysisValidator().validate("we saw T10591 here", cfg, CTX)
    assert near.correct is False
    exact = await ReportAnalysisValidator().validate("we saw T1059 here", cfg, CTX)
    assert exact.correct is True


async def test_section_whole_word_match() -> None:
    cfg = {"sections_required": ["summary"]}
    # "summarised" should not satisfy the "summary" section.
    res = await ReportAnalysisValidator().validate("I summarised it", cfg, CTX)
    assert res.correct is False


async def test_case_insensitive_by_default() -> None:
    cfg = {"must_mention_iocs": ["EvIl.Example"], "sections_required": ["Summary"]}
    res = await ReportAnalysisValidator().validate(
        "## summary\nsaw evil.example", cfg, CTX
    )
    assert res.correct is True


async def test_case_sensitive_when_requested() -> None:
    cfg = {"must_mention_iocs": ["Evil.Example"], "case_sensitive": True}
    res = await ReportAnalysisValidator().validate("saw evil.example", cfg, CTX)
    assert res.correct is False
    assert "Evil.Example" in res.details["missing_iocs"]


async def test_empty_rubric_raises() -> None:
    with pytest.raises(ValidatorConfigError):
        await ReportAnalysisValidator().validate("anything", {}, CTX)


async def test_bad_config_type_raises() -> None:
    with pytest.raises(ValidatorConfigError):
        await ReportAnalysisValidator().validate(
            "x", {"must_mention_iocs": "not-a-list"}, CTX
        )
