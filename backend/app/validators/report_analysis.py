"""Rule-based incident-report analysis validator (BACKLOG: report-analysis).

Implements the deterministic half of the recommended hybrid design: a
gate that scores a player's written incident report on completeness
against an author-supplied rubric. The (non-deterministic) LLM
qualitative critique is intentionally out of scope here — this gate is
fully deterministic so it can drop a flag, and the LLM pass can layer on
top later as advisory feedback.

The submission is the report text (e.g. the ``incident-report.md`` the
player wrote). Config is the rubric::

    {
      "must_mention_iocs": ["192.0.2.10", "evil.example", "d41d8cd98f00..."],
      "must_cite_techniques": ["T1059", "T1071.001"],
      "sections_required": ["summary", "timeline", "iocs", "containment",
                            "recommendations"],
      "case_sensitive": false
    }

Correct == every required IOC is mentioned AND every required ATT&CK
technique is cited AND every required section heading is present. The
returned ``details`` carry a per-dimension breakdown (what's missing +
a 0..1 completeness score) so the player gets actionable feedback, not
just pass/fail.
"""

from __future__ import annotations

import re
from typing import Any, List, Mapping

from bluerange_spec import (
    ValidationContext,
    ValidationResult,
    Validator,
    ValidatorConfigError,
)


def _coerce_str_list(
    config: Mapping[str, Any], key: str, who: str
) -> List[str]:
    raw = config.get(key)
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValidatorConfigError(f"{who} validator: '{key}' must be a list")
    if not all(isinstance(x, str) and x for x in raw):
        raise ValidatorConfigError(
            f"{who} validator: every '{key}' entry must be a non-empty string"
        )
    return raw


class ReportAnalysisValidator(Validator):
    name = "report_analysis"
    requires_subprocess = False
    default_timeout_s = 2.0

    async def validate(
        self,
        submission: str,
        config: Mapping[str, Any],
        context: ValidationContext,
    ) -> ValidationResult:
        who = self.name
        iocs = _coerce_str_list(config, "must_mention_iocs", who)
        techniques = _coerce_str_list(config, "must_cite_techniques", who)
        sections = _coerce_str_list(config, "sections_required", who)

        if not (iocs or techniques or sections):
            raise ValidatorConfigError(
                f"{who} validator requires at least one of "
                "'must_mention_iocs', 'must_cite_techniques', "
                "'sections_required'"
            )

        case_sensitive = bool(config.get("case_sensitive", False))
        haystack = submission if case_sensitive else submission.lower()

        # IOCs: literal substring match (IOCs contain regex metachars like
        # dots in IPs/domains, so we don't treat them as patterns).
        missing_iocs = [
            ioc
            for ioc in iocs
            if (ioc if case_sensitive else ioc.lower()) not in haystack
        ]

        # ATT&CK technique IDs: whole-token match so "T1059" doesn't match
        # inside "T10591". Sub-technique dotted IDs are matched exactly.
        flags = 0 if case_sensitive else re.IGNORECASE
        missing_techniques = [
            tech
            for tech in techniques
            if not re.search(rf"(?<![\w.]){re.escape(tech)}(?![\w.])", submission, flags)
        ]

        # Sections: the heading keyword must appear as a whole word
        # (covers "## Summary", "Summary:", "SUMMARY").
        missing_sections = [
            sec
            for sec in sections
            if not re.search(rf"\b{re.escape(sec)}\b", submission, flags)
        ]

        total = len(iocs) + len(techniques) + len(sections)
        missing = len(missing_iocs) + len(missing_techniques) + len(missing_sections)
        # total > 0 guaranteed by the config check above.
        score = round((total - missing) / total, 3)
        correct = missing == 0

        return ValidationResult(
            correct=correct,
            details={
                "score": score,
                "missing_iocs": missing_iocs,
                "missing_techniques": missing_techniques,
                "missing_sections": missing_sections,
                "iocs_total": len(iocs),
                "techniques_total": len(techniques),
                "sections_total": len(sections),
            },
        )


__all__ = ["ReportAnalysisValidator"]
