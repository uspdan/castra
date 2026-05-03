"""Unit tests for the three pure-Python Phase 10 validators.

chain_of_custody / attack_chain / cloud_misconfig — all run on the
event loop without subprocess sandboxing.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from app.validators.attack_chain import AttackChainValidator
from app.validators.chain_of_custody import ChainOfCustodyValidator
from app.validators.cloud_misconfig import CloudMisconfigValidator
from bluerange_spec import ValidationContext, ValidatorConfigError


@pytest.fixture
def context():
    return ValidationContext(flag_id="f1", challenge_slug="c1")


def _h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# ChainOfCustodyValidator
# ---------------------------------------------------------------------------
class TestChainOfCustody:
    def _config(self, *, expected_steps=None, allowed_actors=None, final=None):
        cfg: dict = {
            "expected_steps": expected_steps or ["acquire", "transport", "image"],
            "allowed_actors": allowed_actors or ["alice", "bob"],
        }
        if final:
            cfg["expected_final_hash"] = final
        return cfg

    def _chain(self, h0, h1, h2):
        return [
            {
                "actor": "alice",
                "action": "acquire",
                "timestamp": "2026-04-01T08:00:00Z",
                "this_hash": h0,
                "prev_hash": None,
            },
            {
                "actor": "bob",
                "action": "transport",
                "timestamp": "2026-04-01T09:00:00Z",
                "this_hash": h1,
                "prev_hash": h0,
            },
            {
                "actor": "alice",
                "action": "image",
                "timestamp": "2026-04-01T10:00:00Z",
                "this_hash": h2,
                "prev_hash": h1,
            },
        ]

    async def test_happy_path(self, context):
        v = ChainOfCustodyValidator()
        h0, h1, h2 = _h(b"a"), _h(b"b"), _h(b"c")
        chain = self._chain(h0, h1, h2)
        r = await v.validate(json.dumps(chain), self._config(final=h2), context)
        assert r.correct is True

    async def test_chain_break_detected(self, context):
        v = ChainOfCustodyValidator()
        h0, h1, h2 = _h(b"a"), _h(b"b"), _h(b"c")
        chain = self._chain(h0, h1, h2)
        chain[1]["prev_hash"] = _h(b"tampered")
        r = await v.validate(json.dumps(chain), self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "chain_break"

    async def test_non_monotonic_timestamps(self, context):
        v = ChainOfCustodyValidator()
        h0, h1, h2 = _h(b"a"), _h(b"b"), _h(b"c")
        chain = self._chain(h0, h1, h2)
        chain[2]["timestamp"] = "2026-04-01T08:30:00Z"
        r = await v.validate(json.dumps(chain), self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "non_monotonic"

    async def test_unknown_actor(self, context):
        v = ChainOfCustodyValidator()
        h0, h1, h2 = _h(b"a"), _h(b"b"), _h(b"c")
        chain = self._chain(h0, h1, h2)
        chain[1]["actor"] = "intruder"
        r = await v.validate(json.dumps(chain), self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "actor"

    async def test_naive_timestamp_rejected(self, context):
        v = ChainOfCustodyValidator()
        h0, h1, h2 = _h(b"a"), _h(b"b"), _h(b"c")
        chain = self._chain(h0, h1, h2)
        chain[0]["timestamp"] = "2026-04-01T08:00:00"  # no zone
        r = await v.validate(json.dumps(chain), self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "timestamp"

    async def test_step_count_mismatch(self, context):
        v = ChainOfCustodyValidator()
        h0, h1, h2 = _h(b"a"), _h(b"b"), _h(b"c")
        chain = self._chain(h0, h1, h2)[:2]
        r = await v.validate(json.dumps(chain), self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "step_count"

    async def test_first_prev_hash_must_be_null(self, context):
        v = ChainOfCustodyValidator()
        h0, h1, h2 = _h(b"a"), _h(b"b"), _h(b"c")
        chain = self._chain(h0, h1, h2)
        chain[0]["prev_hash"] = _h(b"x")
        r = await v.validate(json.dumps(chain), self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "first_prev_hash_must_be_null"

    async def test_final_hash_mismatch(self, context):
        v = ChainOfCustodyValidator()
        h0, h1, h2 = _h(b"a"), _h(b"b"), _h(b"c")
        chain = self._chain(h0, h1, h2)
        r = await v.validate(
            json.dumps(chain), self._config(final=_h(b"different")), context
        )
        assert r.correct is False
        assert r.details["reason"] == "final_hash"

    async def test_invalid_json_returns_false(self, context):
        v = ChainOfCustodyValidator()
        r = await v.validate("not json", self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "not_json"

    async def test_config_validation_errors(self, context):
        v = ChainOfCustodyValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("[]", {"expected_steps": [], "allowed_actors": ["x"]}, context)
        with pytest.raises(ValidatorConfigError):
            await v.validate(
                "[]", {"expected_steps": ["a"], "allowed_actors": []}, context
            )
        with pytest.raises(ValidatorConfigError):
            await v.validate(
                "[]",
                {
                    "expected_steps": ["a"],
                    "allowed_actors": ["x"],
                    "expected_final_hash": "not-hex",
                },
                context,
            )


# ---------------------------------------------------------------------------
# AttackChainValidator
# ---------------------------------------------------------------------------
class TestAttackChain:
    async def test_exact_match_happy(self, context):
        v = AttackChainValidator()
        config = {"required_chain": ["T1566.001", "T1059.001", "T1486"]}
        r = await v.validate("T1566.001 -> T1059.001 -> T1486", config, context)
        assert r.correct is True

    async def test_arrow_and_comma_separators(self, context):
        v = AttackChainValidator()
        config = {"required_chain": ["T1566", "T1059", "T1486"]}
        r = await v.validate("T1566, T1059; T1486", config, context)
        assert r.correct is True

    async def test_wrong_order_fails(self, context):
        v = AttackChainValidator()
        config = {"required_chain": ["T1566.001", "T1059.001", "T1486"]}
        r = await v.validate("T1059.001 T1566.001 T1486", config, context)
        assert r.correct is False
        assert r.details["reason"] == "exact_match"

    async def test_invalid_technique_id(self, context):
        v = AttackChainValidator()
        config = {"required_chain": ["T1566.001"]}
        r = await v.validate("T156.001 T1059.001", config, context)
        assert r.correct is False
        assert r.details["reason"] == "bad_token"

    async def test_distractors_allowed(self, context):
        v = AttackChainValidator()
        config = {
            "required_chain": ["T1566.001", "T1486"],
            "allow_distractors": True,
            "min_steps": 2,
            "max_steps": 8,
        }
        r = await v.validate(
            "T1566.001 -> T1059.001 -> T1003 -> T1486", config, context
        )
        assert r.correct is True

    async def test_distractor_chain_missing_required(self, context):
        v = AttackChainValidator()
        config = {
            "required_chain": ["T1566.001", "T1486"],
            "allow_distractors": True,
            "min_steps": 2,
        }
        r = await v.validate("T1566.001 T1059.001 T1003", config, context)
        assert r.correct is False
        assert r.details["reason"] == "missing_required"
        assert r.details["matched_up_to"] == 1

    async def test_normalises_case_and_dups(self, context):
        v = AttackChainValidator()
        config = {"required_chain": ["T1566.001", "T1059.001"]}
        r = await v.validate("t1566.001 T1566.001 -> T1059.001", config, context)
        assert r.correct is True

    async def test_step_count_oob(self, context):
        v = AttackChainValidator()
        config = {"required_chain": ["T1566.001"], "min_steps": 5}
        r = await v.validate("T1566.001", config, context)
        assert r.correct is False
        assert r.details["reason"] == "step_count"

    async def test_config_validation(self, context):
        v = AttackChainValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("", {"required_chain": []}, context)
        with pytest.raises(ValidatorConfigError):
            await v.validate("", {"required_chain": ["bogus"]}, context)


# ---------------------------------------------------------------------------
# CloudMisconfigValidator
# ---------------------------------------------------------------------------
class TestCloudMisconfig:
    def _config(self, **overrides):
        cfg: dict = {
            "expected_findings": [
                {
                    "resource": "aws_s3_bucket.public",
                    "finding": "PUBLIC_READ_ACL",
                    "severity": "critical",
                },
                {
                    "resource": "aws_security_group.wide",
                    "finding": "INGRESS_0_0_0_0_22",
                    "severity": "high",
                },
                {
                    "resource": "aws_iam_role.over",
                    "finding": "STAR_ACTION",
                    "severity": "medium",
                },
            ],
        }
        cfg.update(overrides)
        return cfg

    async def test_full_match_happy(self, context):
        v = CloudMisconfigValidator()
        sub = json.dumps([
            {"resource": "aws_s3_bucket.public", "finding": "PUBLIC_READ_ACL"},
            {"resource": "aws_security_group.wide", "finding": "INGRESS_0_0_0_0_22"},
            {"resource": "aws_iam_role.over", "finding": "STAR_ACTION"},
        ])
        r = await v.validate(sub, self._config(), context)
        assert r.correct is True
        assert r.details["matched"] == 3

    async def test_partial_fails_when_min_findings_high(self, context):
        v = CloudMisconfigValidator()
        sub = json.dumps([
            {"resource": "aws_s3_bucket.public", "finding": "PUBLIC_READ_ACL"},
        ])
        r = await v.validate(sub, self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "insufficient"

    async def test_unknown_finding_rejected_by_default(self, context):
        v = CloudMisconfigValidator()
        sub = json.dumps([
            {"resource": "aws_s3_bucket.public", "finding": "PUBLIC_READ_ACL"},
            {"resource": "aws_s3_bucket.public", "finding": "FAKE_FINDING"},
        ])
        r = await v.validate(sub, self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "unknown_findings"

    async def test_extra_allowed_when_flagged(self, context):
        v = CloudMisconfigValidator()
        sub = json.dumps([
            {"resource": "aws_s3_bucket.public", "finding": "PUBLIC_READ_ACL"},
            {"resource": "aws_security_group.wide", "finding": "INGRESS_0_0_0_0_22"},
            {"resource": "aws_iam_role.over", "finding": "STAR_ACTION"},
            {"resource": "aws_s3_bucket.public", "finding": "FAKE_FINDING"},
        ])
        r = await v.validate(sub, self._config(allow_extra=True), context)
        assert r.correct is True

    async def test_must_include_severity_blocks_partial(self, context):
        v = CloudMisconfigValidator()
        sub = json.dumps([
            {"resource": "aws_security_group.wide", "finding": "INGRESS_0_0_0_0_22"},
            {"resource": "aws_iam_role.over", "finding": "STAR_ACTION"},
        ])
        r = await v.validate(
            sub,
            self._config(min_findings=2, must_include_severities=["critical"]),
            context,
        )
        assert r.correct is False
        assert r.details["reason"] == "missing_critical"

    async def test_invalid_json(self, context):
        v = CloudMisconfigValidator()
        r = await v.validate("not json", self._config(), context)
        assert r.correct is False
        assert r.details["reason"] == "not_json"

    async def test_config_validation(self, context):
        v = CloudMisconfigValidator()
        with pytest.raises(ValidatorConfigError):
            await v.validate("[]", {"expected_findings": []}, context)
        with pytest.raises(ValidatorConfigError):
            await v.validate(
                "[]",
                {"expected_findings": [{"resource": "x", "finding": "y"}], "min_findings": 5},
                context,
            )
