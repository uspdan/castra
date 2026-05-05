"""Loader integration tests against the testcontainer DB.

Covers:

- happy-path dry-run on the example challenges
- happy-path apply: rows materialise in challenges / challenge_flags /
  challenge_artifacts, with sane values
- second apply on unchanged manifest is idempotent (status=unchanged,
  no new rows)
- mutating the manifest changes manifest_sha256 and forces
  pending_review=true + is_released=false
- a tampered artifact file is rejected with status=artifact_mismatch
- a malformed manifest is rejected with status=invalid
- a manifest with an unknown extra field is rejected
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models import Challenge, ChallengeArtifact, ChallengeFlag
from app.services.challenge_loader import LoadStatus, run

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "examples" / "challenges"


@pytest.fixture
def staged_examples(tmp_path: Path) -> Path:
    """Copy ``examples/challenges`` into a writable scratch dir."""

    dest = tmp_path / "challenges"
    shutil.copytree(EXAMPLES, dest)
    return dest


_EXPECTED_EXAMPLE_SLUGS = {
    "soc-001-off-hours-admin",
    "dfir-001-memory-string",
    "soc-002-pwsh-detection",
    "llm-customer-pii",
}


async def test_dry_run_loads_examples(staged_examples: Path) -> None:
    report = await run([staged_examples], db=None, dry_run=True)
    assert report.failure_count == 0, report.outcomes
    statuses = {o.slug: o.status for o in report.outcomes}
    assert statuses == {slug: LoadStatus.LOADED for slug in _EXPECTED_EXAMPLE_SLUGS}


async def test_apply_creates_rows(db_session, staged_examples: Path) -> None:
    report = await run([staged_examples], db=db_session, dry_run=False)
    assert report.failure_count == 0
    assert {o.slug for o in report.outcomes} == _EXPECTED_EXAMPLE_SLUGS
    # Newly inserted challenges → pending_review.
    for o in report.outcomes:
        assert o.status == LoadStatus.PENDING_REVIEW

    soc = await _fetch_challenge(db_session, "soc-001-off-hours-admin")
    assert soc is not None
    assert soc.spec_version == "1"
    assert soc.manifest_sha256 and len(soc.manifest_sha256) == 64
    assert soc.license == "CC-BY-4.0"
    assert soc.author_json == {
        "name": "seige-range maintainers",
        "email": None,
        "url": "https://github.com/seige-range",
    }
    assert soc.pending_review is True
    assert soc.is_released is False
    assert soc.flag_hash is not None  # legacy column populated

    flags = await _fetch_flags(db_session, soc.id)
    assert len(flags) == 1
    assert flags[0].flag_id == "elevation_ts"
    assert flags[0].flag_type == "exact"
    assert flags[0].value_hash and len(flags[0].value_hash) == 64

    artifacts = await _fetch_artifacts(db_session, soc.id)
    assert len(artifacts) == 1
    assert artifacts[0].path == "artifacts/auth.log"


async def test_apply_is_idempotent(db_session, staged_examples: Path) -> None:
    first = await run([staged_examples], db=db_session, dry_run=False)
    assert first.failure_count == 0
    second = await run([staged_examples], db=db_session, dry_run=False)
    assert second.failure_count == 0
    statuses = {o.slug: o.status for o in second.outcomes}
    assert statuses == {slug: LoadStatus.UNCHANGED for slug in _EXPECTED_EXAMPLE_SLUGS}


async def test_manifest_drift_marks_pending_review(
    db_session, staged_examples: Path
) -> None:
    await run([staged_examples], db=db_session, dry_run=False)
    soc_dir = staged_examples / "soc-001-off-hours-admin"
    manifest = soc_dir / "manifest.yaml"

    # Operator clears pending_review (as if they reviewed + released).
    soc = await _fetch_challenge(db_session, "soc-001-off-hours-admin")
    soc.pending_review = False
    soc.is_released = True
    await db_session.commit()

    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text.replace("difficulty: 1", "difficulty: 2"), encoding="utf-8")

    report = await run([staged_examples], db=db_session, dry_run=False)
    assert report.failure_count == 0
    soc_status = next(
        o for o in report.outcomes if o.slug == "soc-001-off-hours-admin"
    ).status
    assert soc_status == LoadStatus.PENDING_REVIEW

    refreshed = await _fetch_challenge(db_session, "soc-001-off-hours-admin")
    assert refreshed.pending_review is True
    assert refreshed.is_released is False
    assert refreshed.difficulty == 2


async def test_artifact_mismatch_rejected(
    db_session, staged_examples: Path
) -> None:
    log = staged_examples / "soc-001-off-hours-admin" / "artifacts" / "auth.log"
    log.write_text("tampered\n", encoding="utf-8")

    report = await run([staged_examples], db=db_session, dry_run=False)
    soc = next(
        o for o in report.outcomes if str(o.directory).endswith("soc-001-off-hours-admin")
    )
    assert soc.status == LoadStatus.ARTIFACT_MISMATCH
    assert "auth.log" in soc.detail


async def test_invalid_manifest_rejected(
    db_session, tmp_path: Path
) -> None:
    bad = tmp_path / "bad-challenge"
    bad.mkdir()
    (bad / "manifest.yaml").write_text(
        "spec_version: '1'\nslug: 'BAD slug'\n", encoding="utf-8"
    )
    report = await run([bad], db=db_session, dry_run=False)
    assert len(report.outcomes) == 1
    assert report.outcomes[0].status == LoadStatus.INVALID


async def test_unknown_field_rejected(
    db_session, staged_examples: Path
) -> None:
    manifest = staged_examples / "soc-001-off-hours-admin" / "manifest.yaml"
    text = manifest.read_text(encoding="utf-8")
    manifest.write_text(text + "\nbogus_field: 'nope'\n", encoding="utf-8")
    report = await run([staged_examples], db=db_session, dry_run=False)
    soc = next(o for o in report.outcomes if "soc-001" in str(o.directory))
    assert soc.status == LoadStatus.INVALID


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _fetch_challenge(db, slug: str) -> Challenge | None:
    res = await db.execute(select(Challenge).where(Challenge.slug == slug))
    return res.scalar_one_or_none()


async def _fetch_flags(db, challenge_id: int) -> list[ChallengeFlag]:
    res = await db.execute(
        select(ChallengeFlag).where(ChallengeFlag.challenge_id == challenge_id)
    )
    return list(res.scalars())


async def _fetch_artifacts(db, challenge_id: int) -> list[ChallengeArtifact]:
    res = await db.execute(
        select(ChallengeArtifact).where(ChallengeArtifact.challenge_id == challenge_id)
    )
    return list(res.scalars())
