"""Offline challenge test harness.

Authors declare ``tests.cases`` in their manifest; the harness loads
the manifest (without touching the platform DB), instantiates the
named validator for each case, dispatches the submission through the
same sandbox + artefact-staging path the API uses, and reports
pass/fail.

Public surface:

- :class:`HarnessOutcome`, :class:`CaseOutcome`, :class:`CaseStatus` —
  structured per-case + per-challenge result types.
- :func:`run_case` — execute a single :class:`bluerange_spec.TestCase`.
- :func:`run_challenge` — execute every test case for a single
  challenge directory.
- :func:`run_paths` — walk one or more roots, returning a flat report.

The harness reuses the platform's validator registry so behavioural
equivalence with the API is automatic — anything that lands in
``app.validators`` (or a third-party plugin under the
``bluerange.validators`` entry-point group) is exercised the same way
on both code paths.
"""

from .runner import (
    CaseOutcome,
    CaseStatus,
    HarnessOutcome,
    HarnessReport,
    run_case,
    run_challenge,
    run_paths,
    run_paths_sync,
)

__all__ = [
    "CaseOutcome",
    "CaseStatus",
    "HarnessOutcome",
    "HarnessReport",
    "run_case",
    "run_challenge",
    "run_paths",
    "run_paths_sync",
]
