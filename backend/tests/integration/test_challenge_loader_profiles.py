"""Phase 9 — loader: profile registry validation + missing-digest warnings."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from app.services.challenge_loader import LoadStatus, run


REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "examples" / "challenges"


@pytest.fixture
def staged_examples(tmp_path: Path) -> Path:
    dest = tmp_path / "challenges"
    shutil.copytree(EXAMPLES, dest)
    return dest


async def _patch_manifest(directory: Path, mutator) -> None:
    path = directory / "manifest.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutator(raw)
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


async def test_default_strict_profile_loads_clean(staged_examples: Path) -> None:
    """Existing examples use default-strict. Phase 9 must not break them."""
    report = await run([staged_examples], db=None, dry_run=True)
    assert report.failure_count == 0
    statuses = {o.slug: o.status for o in report.outcomes}
    expected = {
        "soc-001-off-hours-admin",
        "dfir-001-memory-string",
        "soc-002-pwsh-detection",
        "llm-customer-pii",
    }
    assert statuses == {slug: LoadStatus.LOADED for slug in expected}


async def test_unknown_profile_rejected(staged_examples: Path) -> None:
    soc = staged_examples / "soc-001-off-hours-admin"
    await _patch_manifest(soc, lambda d: d["container"].__setitem__("profile", "rogue-mode"))

    report = await run([soc], db=None, dry_run=True)
    assert report.failure_count == 1
    outcome = report.outcomes[0]
    assert outcome.status == LoadStatus.UNKNOWN_PROFILE
    assert "rogue-mode" in outcome.detail


async def test_missing_digest_loads_with_warning(staged_examples: Path) -> None:
    """Phase 9: digest is required at LAUNCH; load surfaces a warning."""
    report = await run([staged_examples], db=None, dry_run=True)
    soc = next(o for o in report.outcomes if o.slug == "soc-001-off-hours-admin")
    # Existing examples ship without digest, so we expect a warning.
    assert soc.warnings
    assert any("digest" in w.lower() for w in soc.warnings)


async def test_pinned_digest_loads_without_warning(staged_examples: Path) -> None:
    soc = staged_examples / "soc-001-off-hours-admin"
    await _patch_manifest(
        soc,
        lambda d: d["container"].__setitem__("digest", "sha256:" + "0" * 64),
    )
    report = await run([soc], db=None, dry_run=True)
    outcome = report.outcomes[0]
    assert outcome.status == LoadStatus.LOADED
    assert not any("digest" in w.lower() for w in outcome.warnings)
