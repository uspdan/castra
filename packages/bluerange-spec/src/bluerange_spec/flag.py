"""Flag definitions.

A v1 manifest may declare one or more flags. Each carries a ``type``
discriminator naming the validator plugin that will check submissions
against it. v1 ships three first-party validator types:

- ``exact`` — case-sensitive whole-string equality.
- ``regex`` — regular expression match (engine: re by default;
  ``google-re2`` will be substituted by the platform when available
  per Phase 8 decision).
- ``multi_part`` — ordered list of sub-flags that must all be submitted.

Phase 10 added five blue-team validators with their own typed flag
classes:

- ``sigma_rule`` — Sigma rule the player writes to detect a fixture
  event log; matched indices must equal the manifest's expected set.
- ``yara_rule`` — YARA rule that must fire on positive samples and
  miss on negative samples, both staged under ``artifact_dir``.
- ``chain_of_custody`` — JSON evidence-handling chain validated
  against an ordered step vocabulary and SHA-256 chain rules.
- ``attack_chain`` — ordered MITRE ATT&CK technique sequence; either
  exact match or subsequence-with-distractors per manifest.
- ``cloud_misconfig`` — set of (resource, finding) pairs the player
  enumerates from a fixture IaC bundle.

Custom validator plugins are introduced via the
``bluerange.validators`` entry-point group; their ``type`` strings are
not constrained by this enum, so the manifest stores ``type`` as a
string and the registry resolves it at submission time. v1's first-
party set is enforced with discriminated-union models below for IDE /
schema friendliness.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


FlagType = Literal[
    "exact",
    "regex",
    "multi_part",
    "sigma_rule",
    "yara_rule",
    "chain_of_custody",
    "attack_chain",
    "cloud_misconfig",
    "llm_signal",
]


class _BaseFlag(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]{0,62}[a-z0-9]$|^[a-z0-9]$")
    points: int = Field(ge=0, le=100_000)
    label: Optional[str] = Field(default=None, max_length=200)


class ExactFlag(_BaseFlag):
    type: Literal["exact"] = "exact"
    value: str = Field(min_length=1, max_length=4096)
    case_sensitive: bool = True


class RegexFlag(_BaseFlag):
    type: Literal["regex"] = "regex"
    pattern: str = Field(min_length=1, max_length=4096)
    case_sensitive: bool = True

    @field_validator("pattern")
    @classmethod
    def _compileable(cls, v: str) -> str:
        import re

        try:
            re.compile(v)
        except re.error as exc:
            raise ValueError(f"regex does not compile: {exc}") from exc
        return v


class MultiPartFlag(_BaseFlag):
    type: Literal["multi_part"] = "multi_part"
    parts: List[str] = Field(min_length=2, max_length=20)
    ordered: bool = True


class SigmaRuleFlag(_BaseFlag):
    """Player must submit a Sigma rule that detects exactly the
    manifest's expected event indices.

    ``events_filename`` references a JSON file under the challenge's
    artefact directory containing a list of event objects. The
    platform stages a read-only copy at submission time and exposes
    its path via :class:`ValidationContext.artifact_dir`.
    """

    type: Literal["sigma_rule"] = "sigma_rule"
    events_filename: str = Field(min_length=1, max_length=200)
    expected_match_indices: List[int] = Field(min_length=1, max_length=4096)
    require_logsource: Optional[Dict[str, str]] = None

    @field_validator("expected_match_indices")
    @classmethod
    def _non_negative(cls, v: List[int]) -> List[int]:
        if any(i < 0 for i in v):
            raise ValueError("expected_match_indices entries must be non-negative")
        return v

    @field_validator("require_logsource")
    @classmethod
    def _logsource_keys(cls, v: Optional[Dict[str, str]]) -> Optional[Dict[str, str]]:
        if v is None:
            return v
        allowed = {"category", "product", "service"}
        unknown = set(v) - allowed
        if unknown:
            raise ValueError(
                f"require_logsource keys must be a subset of {sorted(allowed)}"
            )
        return v


class YaraRuleFlag(_BaseFlag):
    """Player must submit a YARA rule that matches every positive
    sample and misses every negative sample under ``samples_dir``."""

    type: Literal["yara_rule"] = "yara_rule"
    samples_dir: str = Field(default="samples", min_length=1, max_length=64)
    expected_matches: List[str] = Field(min_length=1, max_length=64)
    expected_no_match: List[str] = Field(default_factory=list, max_length=64)
    max_sample_bytes: Optional[int] = Field(default=None, ge=1, le=16 * 1024 * 1024)

    @field_validator("samples_dir", "expected_matches", "expected_no_match")
    @classmethod
    def _no_path_traversal(cls, v):
        items = v if isinstance(v, list) else [v]
        for item in items:
            if "/" in item or ".." in item or item.startswith("."):
                raise ValueError(
                    "values must be bare filenames or directory names "
                    "(no '/', no leading '.', no '..')"
                )
        return v


class ChainOfCustodyFlag(_BaseFlag):
    """Player must submit a JSON chain-of-custody timeline that satisfies
    the configured step vocabulary, actor allowlist, and hash chain."""

    type: Literal["chain_of_custody"] = "chain_of_custody"
    expected_steps: List[str] = Field(min_length=1, max_length=64)
    allowed_actors: List[str] = Field(min_length=1, max_length=64)
    expected_final_hash: Optional[str] = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )


class AttackChainFlag(_BaseFlag):
    """Player must submit an ordered list of MITRE ATT&CK technique IDs
    that satisfies ``required_chain``."""

    type: Literal["attack_chain"] = "attack_chain"
    required_chain: List[str] = Field(min_length=1, max_length=32)
    allow_distractors: bool = False
    min_steps: Optional[int] = Field(default=None, ge=1, le=32)
    max_steps: Optional[int] = Field(default=None, ge=1, le=32)

    @field_validator("required_chain")
    @classmethod
    def _valid_techniques(cls, v: List[str]) -> List[str]:
        import re as _re

        tech_re = _re.compile(r"^T\d{4}(?:\.\d{3})?$")
        out: List[str] = []
        for item in v:
            normalised = item.strip().upper()
            if not tech_re.match(normalised):
                raise ValueError(
                    f"required_chain entry {item!r} is not a valid ATT&CK "
                    "technique ID"
                )
            out.append(normalised)
        return out


class CloudMisconfigFinding(BaseModel):
    """A single (resource, finding, severity) tuple in the expected
    answer key."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    resource: str = Field(min_length=1, max_length=200)
    finding: str = Field(min_length=1, max_length=200)
    severity: str = Field(default="info", min_length=1, max_length=32)


class CloudMisconfigFlag(_BaseFlag):
    """Player must enumerate every cloud misconfiguration in the answer
    key (set equality, unordered) — possibly with extra distractors."""

    type: Literal["cloud_misconfig"] = "cloud_misconfig"
    expected_findings: List[CloudMisconfigFinding] = Field(
        min_length=1, max_length=256
    )
    must_include_severities: List[str] = Field(default_factory=list, max_length=8)
    min_findings: Optional[int] = Field(default=None, ge=1, le=256)
    allow_extra: bool = False


class LlmSignalFlag(_BaseFlag):
    """LLM honeypot signal flag (ADR 0001 / Sprint 9 Phase C).

    Player POSTs a captured LLM transcript; the validator regex-
    matches against ``patterns`` and considers the flag captured
    when at least ``min_matches`` patterns hit anywhere in the
    transcript. Bait secrecy is intentionally out of scope at the
    manifest level — patterns ride in plaintext for self-hosted
    deployments. The encrypted-bundle path described in ADR 0001
    is queued for a future iteration when private-challenge-set
    distribution becomes a concern.
    """

    type: Literal["llm_signal"] = "llm_signal"
    patterns: List[str] = Field(min_length=1, max_length=32)
    case_sensitive: bool = False
    min_matches: int = Field(default=1, ge=1, le=32)

    @field_validator("patterns")
    @classmethod
    def _patterns_compile(cls, v: List[str]) -> List[str]:
        import re

        for p in v:
            if not isinstance(p, str) or not p:
                raise ValueError("patterns entries must be non-empty strings")
            try:
                re.compile(p)
            except re.error as exc:
                raise ValueError(f"pattern does not compile: {p!r}: {exc}") from exc
        return v


Flag = Union[
    ExactFlag,
    RegexFlag,
    MultiPartFlag,
    SigmaRuleFlag,
    YaraRuleFlag,
    ChainOfCustodyFlag,
    AttackChainFlag,
    CloudMisconfigFlag,
    LlmSignalFlag,
]
"""Discriminated union of all first-party flag types.

Pydantic will dispatch on the ``type`` field at validation time. v1
shipped the first three; Phase 10 added the blue-team five.
"""
