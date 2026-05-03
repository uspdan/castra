"""Integration tests for the Phase 10 blue-team validators.

Two flavours:

1. Pure-Python validators (chain_of_custody, attack_chain,
   cloud_misconfig) drive the public ``/submit`` endpoint and assert
   the dispatch -> registry -> validator -> audit pipeline matches.
2. Subprocess-sandboxed validators (sigma_rule, yara_rule) need an
   on-disk artefact directory; we stage one under a tempdir and set
   ``challenge.source_path`` so the dispatch wraps the call in
   ``readonly_artifact_dir``. The full subprocess path runs.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import AuditLedger, Challenge, ChallengeFlag, Solve, TeamType


pytestmark = pytest.mark.integration


def _h(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


async def _make_v1_blue_challenge(
    db_session,
    *,
    slug: str,
    flags: list[ChallengeFlag],
    source_path: str | None = None,
) -> Challenge:
    challenge = Challenge(
        slug=slug,
        title=f"Blue {slug}",
        description="Phase 10 blue-team challenge",
        category="forensics",
        team=TeamType.blue,
        difficulty=2,
        points=200,
        flag_hash=None,
        hints=[],
        skills=[],
        mitre_techniques=[],
        docker_image="alpine:3.19",
        docker_port=80,
        docker_config={},
        prerequisite_ids=[],
        is_active=True,
        is_released=True,
        released_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        spec_version="1",
        source_path=source_path,
    )
    db_session.add(challenge)
    await db_session.commit()
    await db_session.refresh(challenge)
    for f in flags:
        f.challenge_id = challenge.id
        db_session.add(f)
    await db_session.commit()
    await db_session.refresh(challenge)
    return challenge


# ---------------------------------------------------------------------------
# Pure-Python validators end-to-end
# ---------------------------------------------------------------------------
class TestChainOfCustodyV1:
    async def test_correct_chain_creates_solve(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_blue_challenge(
            db_session,
            slug="v1-coc",
            flags=[
                ChallengeFlag(
                    flag_id="evidence_timeline",
                    flag_type="chain_of_custody",
                    points=200,
                    config={
                        "expected_steps": ["acquire", "transport"],
                        "allowed_actors": ["alice", "bob"],
                    },
                )
            ],
        )
        h0, h1 = _h(b"a"), _h(b"b")
        chain = [
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
        ]
        r = await client.post(
            "/challenges/v1-coc/submit",
            headers=auth_headers(user),
            json={"flag": json.dumps(chain)},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["correct"] is True
        solve = (
            await db_session.execute(
                select(Solve).where(Solve.user_id == user.id)
            )
        ).scalars().first()
        assert solve is not None


class TestAttackChainV1:
    async def test_distractor_path_accepts_required_subsequence(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_blue_challenge(
            db_session,
            slug="v1-attack",
            flags=[
                ChallengeFlag(
                    flag_id="kill_chain",
                    flag_type="attack_chain",
                    points=200,
                    config={
                        "required_chain": ["T1566.001", "T1486"],
                        "allow_distractors": True,
                    },
                )
            ],
        )
        r = await client.post(
            "/challenges/v1-attack/submit",
            headers=auth_headers(user),
            json={"flag": "T1566.001 -> T1059 -> T1486"},
        )
        assert r.status_code == 200
        assert r.json()["correct"] is True


class TestCloudMisconfigV1:
    async def test_full_match_with_critical_severity_required(
        self, client, user_factory, auth_headers, db_session
    ):
        user = await user_factory()
        await _make_v1_blue_challenge(
            db_session,
            slug="v1-cloud",
            flags=[
                ChallengeFlag(
                    flag_id="findings",
                    flag_type="cloud_misconfig",
                    points=200,
                    config={
                        "expected_findings": [
                            {
                                "resource": "aws_s3_bucket.public",
                                "finding": "PUBLIC_READ_ACL",
                                "severity": "critical",
                            },
                            {
                                "resource": "aws_sg.wide",
                                "finding": "INGRESS_0_0_0_0_22",
                                "severity": "high",
                            },
                        ],
                        "must_include_severities": ["critical"],
                        "allow_extra": False,
                    },
                )
            ],
        )
        sub = json.dumps([
            {"resource": "aws_s3_bucket.public", "finding": "PUBLIC_READ_ACL"},
            {"resource": "aws_sg.wide", "finding": "INGRESS_0_0_0_0_22"},
        ])
        r = await client.post(
            "/challenges/v1-cloud/submit",
            headers=auth_headers(user),
            json={"flag": sub},
        )
        assert r.status_code == 200
        assert r.json()["correct"] is True


# ---------------------------------------------------------------------------
# Subprocess-sandboxed validators (sigma_rule + yara_rule)
# ---------------------------------------------------------------------------
class TestSigmaRuleV1:
    async def test_sigma_rule_subprocess_dispatch(
        self, client, user_factory, auth_headers, db_session, tmp_path: Path
    ):
        user = await user_factory()
        # Stage the events fixture under a real on-disk path; set
        # source_path on the challenge so readonly_artifact_dir copies
        # it for the validator.
        events = [
            {"EventID": 4688, "Image": "C:\\Windows\\powershell.exe"},
            {"EventID": 4624, "Image": None},
        ]
        artefact_dir = tmp_path / "challenge"
        artefact_dir.mkdir()
        (artefact_dir / "events.json").write_text(json.dumps(events))
        await _make_v1_blue_challenge(
            db_session,
            slug="v1-sigma",
            source_path=str(artefact_dir),
            flags=[
                ChallengeFlag(
                    flag_id="ps_detection",
                    flag_type="sigma_rule",
                    points=200,
                    config={
                        "events_filename": "events.json",
                        "expected_match_indices": [0],
                    },
                )
            ],
        )
        rule = (
            "title: detect powershell\n"
            "logsource:\n"
            "  product: windows\n"
            "detection:\n"
            "  selection:\n"
            "    EventID: 4688\n"
            "    Image|endswith: '\\\\powershell.exe'\n"
            "  condition: selection\n"
        )
        r = await client.post(
            "/challenges/v1-sigma/submit",
            headers=auth_headers(user),
            json={"flag": rule},
        )
        assert r.status_code == 200, r.text
        assert r.json()["correct"] is True

        # Audit ledger received the v1 metadata so chain-of-custody
        # downstream consumers can attribute the validator name.
        rows = (
            await db_session.execute(
                select(AuditLedger).where(
                    AuditLedger.event_type == "challenge.flag.submit.pass",
                    AuditLedger.actor_id == str(user.id),
                )
            )
        ).scalars().all()
        assert rows
        assert rows[-1].payload["validator"] == "sigma_rule"


class TestYaraRuleV1:
    async def test_yara_rule_subprocess_dispatch(
        self, client, user_factory, auth_headers, db_session, tmp_path: Path
    ):
        user = await user_factory()
        artefact_dir = tmp_path / "yara-challenge"
        artefact_dir.mkdir()
        samples = artefact_dir / "samples"
        samples.mkdir()
        (samples / "evil.bin").write_bytes(b"hello world\n")
        (samples / "clean.bin").write_bytes(b"goodbye\n")
        await _make_v1_blue_challenge(
            db_session,
            slug="v1-yara",
            source_path=str(artefact_dir),
            flags=[
                ChallengeFlag(
                    flag_id="hello_detection",
                    flag_type="yara_rule",
                    points=200,
                    config={
                        "samples_dir": "samples",
                        "expected_matches": ["evil.bin"],
                        "expected_no_match": ["clean.bin"],
                    },
                )
            ],
        )
        rule = (
            'rule hello_world {\n'
            '    strings:\n'
            '        $a = "hello"\n'
            '    condition:\n'
            '        $a\n'
            '}\n'
        )
        r = await client.post(
            "/challenges/v1-yara/submit",
            headers=auth_headers(user),
            json={"flag": rule},
        )
        assert r.status_code == 200, r.text
        assert r.json()["correct"] is True
