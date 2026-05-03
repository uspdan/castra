"""Translate a typed manifest ``Flag`` into validator-dispatch args.

The dispatcher (:mod:`app.services.flag_dispatch`) consumes
``(flag_type, value_hash, config)`` triples — the same shape persisted
into the ``challenge_flags`` table by :mod:`.upsert`. The DB persistence
path and the offline test-harness path both need to derive that shape
from a manifest ``Flag`` instance, so the conversion lives here as a
single source of truth.

Phase 11 introduces the second consumer (the harness). Before this
module the conversion was inlined in ``upsert._flag_row``; that
inline form has been replaced with a call to :func:`flag_to_dispatch`.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from bluerange_spec import (
    AttackChainFlag,
    ChainOfCustodyFlag,
    CloudMisconfigFlag,
    ExactFlag,
    MultiPartFlag,
    RegexFlag,
    SigmaRuleFlag,
    YaraRuleFlag,
)


@dataclass(frozen=True)
class FlagDispatchArgs:
    """The persistable view of a manifest flag.

    This is the input shape :class:`app.models.ChallengeFlag` is built
    from, and the input shape the offline harness feeds to
    :func:`app.services.flag_dispatch.dispatch_submission`.
    """

    flag_id: str
    flag_type: str
    points: int
    label: Optional[str]
    value_hash: Optional[str]
    config: Mapping[str, Any]


def flag_to_dispatch(flag) -> FlagDispatchArgs:
    """Convert a typed manifest flag to a :class:`FlagDispatchArgs`."""

    if isinstance(flag, ExactFlag):
        return FlagDispatchArgs(
            flag_id=flag.id,
            flag_type="exact",
            points=flag.points,
            label=flag.label,
            value_hash=hashlib.sha256(flag.value.encode("utf-8")).hexdigest(),
            config={"case_sensitive": flag.case_sensitive},
        )
    if isinstance(flag, RegexFlag):
        return FlagDispatchArgs(
            flag_id=flag.id,
            flag_type="regex",
            points=flag.points,
            label=flag.label,
            value_hash=None,
            config={"pattern": flag.pattern, "case_sensitive": flag.case_sensitive},
        )
    if isinstance(flag, MultiPartFlag):
        return FlagDispatchArgs(
            flag_id=flag.id,
            flag_type="multi_part",
            points=flag.points,
            label=flag.label,
            value_hash=None,
            config={"parts": list(flag.parts), "ordered": flag.ordered},
        )
    if isinstance(flag, SigmaRuleFlag):
        config: dict = {
            "events_filename": flag.events_filename,
            "expected_match_indices": list(flag.expected_match_indices),
        }
        if flag.require_logsource:
            config["require_logsource"] = dict(flag.require_logsource)
        return FlagDispatchArgs(
            flag_id=flag.id,
            flag_type="sigma_rule",
            points=flag.points,
            label=flag.label,
            value_hash=None,
            config=config,
        )
    if isinstance(flag, YaraRuleFlag):
        config = {
            "samples_dir": flag.samples_dir,
            "expected_matches": list(flag.expected_matches),
            "expected_no_match": list(flag.expected_no_match),
        }
        if flag.max_sample_bytes is not None:
            config["max_sample_bytes"] = flag.max_sample_bytes
        return FlagDispatchArgs(
            flag_id=flag.id,
            flag_type="yara_rule",
            points=flag.points,
            label=flag.label,
            value_hash=None,
            config=config,
        )
    if isinstance(flag, ChainOfCustodyFlag):
        config = {
            "expected_steps": list(flag.expected_steps),
            "allowed_actors": list(flag.allowed_actors),
        }
        if flag.expected_final_hash:
            config["expected_final_hash"] = flag.expected_final_hash
        return FlagDispatchArgs(
            flag_id=flag.id,
            flag_type="chain_of_custody",
            points=flag.points,
            label=flag.label,
            value_hash=None,
            config=config,
        )
    if isinstance(flag, AttackChainFlag):
        config = {
            "required_chain": list(flag.required_chain),
            "allow_distractors": flag.allow_distractors,
        }
        if flag.min_steps is not None:
            config["min_steps"] = flag.min_steps
        if flag.max_steps is not None:
            config["max_steps"] = flag.max_steps
        return FlagDispatchArgs(
            flag_id=flag.id,
            flag_type="attack_chain",
            points=flag.points,
            label=flag.label,
            value_hash=None,
            config=config,
        )
    if isinstance(flag, CloudMisconfigFlag):
        config = {
            "expected_findings": [f.model_dump() for f in flag.expected_findings],
            "must_include_severities": list(flag.must_include_severities),
            "allow_extra": flag.allow_extra,
        }
        if flag.min_findings is not None:
            config["min_findings"] = flag.min_findings
        return FlagDispatchArgs(
            flag_id=flag.id,
            flag_type="cloud_misconfig",
            points=flag.points,
            label=flag.label,
            value_hash=None,
            config=config,
        )
    raise TypeError(f"unsupported flag type: {type(flag).__name__}")
