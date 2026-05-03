"""Persist a validated manifest into the database.

The loader is the only writer of v1 challenges. It is **idempotent**
when run repeatedly against an unchanged manifest, and it sets
``pending_review=true`` on any row whose ``manifest_sha256`` has
changed since the last load — operators must re-release the challenge
through the admin path after reviewing the diff.

This module is intentionally split from :mod:`.single` so the pure
validation half can be tested without a DB.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Challenge, ChallengeArtifact, ChallengeFlag, TeamType, utcnow
from bluerange_spec import ChallengeManifest, ExactFlag

from .flag_mapping import flag_to_dispatch
from .single import LoadedManifest


@dataclass
class UpsertOutcome:
    slug: str
    created: bool
    digest_changed: bool
    pending_review: bool


async def upsert_manifest(
    db: AsyncSession,
    loaded: LoadedManifest,
) -> UpsertOutcome:
    """Insert or update a challenge from a :class:`LoadedManifest`.

    Returns an :class:`UpsertOutcome` describing what happened. The
    caller decides whether to commit the surrounding transaction.
    """

    manifest = loaded.manifest
    existing = await _fetch_by_slug(db, manifest.slug)
    if existing is None:
        challenge = Challenge()
        db.add(challenge)
        created = True
        digest_changed = True
    else:
        challenge = existing
        created = False
        digest_changed = challenge.manifest_sha256 != loaded.manifest_digest

    _apply_manifest_to_challenge(challenge, loaded)
    await db.flush()  # ensures challenge.id is populated for FK rows

    await _replace_flags(db, challenge, manifest)
    await _replace_artifacts(db, challenge, manifest)

    return UpsertOutcome(
        slug=manifest.slug,
        created=created,
        digest_changed=digest_changed,
        pending_review=challenge.pending_review,
    )


async def _fetch_by_slug(db: AsyncSession, slug: str) -> Optional[Challenge]:
    stmt = select(Challenge).where(Challenge.slug == slug)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _apply_manifest_to_challenge(challenge: Challenge, loaded: LoadedManifest) -> None:
    manifest = loaded.manifest
    digest_changed = challenge.manifest_sha256 != loaded.manifest_digest

    challenge.slug = manifest.slug
    challenge.title = manifest.title
    challenge.description = manifest.description
    challenge.category = manifest.category
    challenge.team = TeamType(manifest.team) if manifest.team in ("red", "blue") else TeamType.blue
    challenge.difficulty = manifest.difficulty
    challenge.points = manifest.points
    challenge.skills = list(manifest.skills)
    challenge.mitre_techniques = list(manifest.mitre_techniques)
    challenge.docker_image = manifest.container.image
    challenge.docker_port = manifest.container.port
    challenge.docker_config = {
        "digest": manifest.container.digest,
        "profile": manifest.container.profile,
        "egress_allowlist": list(manifest.container.egress_allowlist or []) or None,
    }
    challenge.hints = [h.model_dump() for h in manifest.hints]
    # Maintain backward compatibility: copy first exact flag's hash to
    # the legacy column so the existing submission path keeps working
    # until Phase 8 swaps it out.
    challenge.flag_hash = _legacy_flag_hash(manifest)
    challenge.spec_version = manifest.spec_version
    challenge.manifest_sha256 = loaded.manifest_digest
    challenge.source_path = str(loaded.directory)
    challenge.loaded_at = utcnow()
    challenge.license = manifest.license
    challenge.author_json = manifest.author.model_dump()
    if digest_changed:
        # New or drifted manifest — operator must re-release.
        challenge.pending_review = True
        challenge.is_released = False


def _legacy_flag_hash(manifest: ChallengeManifest) -> Optional[str]:
    for flag in manifest.flags:
        if isinstance(flag, ExactFlag):
            return hashlib.sha256(flag.value.encode("utf-8")).hexdigest()
    return None


async def _replace_flags(
    db: AsyncSession, challenge: Challenge, manifest: ChallengeManifest
) -> None:
    # Delete-and-reinsert is sufficient for v1: flag identity is the
    # (challenge, flag_id) pair which is regenerated from the manifest
    # on every load. Use a bulk DELETE rather than touching the
    # relationship attribute so we don't trigger a lazy load on a
    # freshly-flushed parent (async SQLAlchemy + selectin lazy loads
    # require an enclosing greenlet that we don't have in this path).
    await db.execute(
        delete(ChallengeFlag).where(ChallengeFlag.challenge_id == challenge.id)
    )
    await db.flush()
    for flag in manifest.flags:
        db.add(_flag_row(challenge.id, flag))


def _flag_row(challenge_id: int, flag) -> ChallengeFlag:
    args = flag_to_dispatch(flag)
    return ChallengeFlag(
        challenge_id=challenge_id,
        flag_id=args.flag_id,
        flag_type=args.flag_type,
        points=args.points,
        label=args.label,
        value_hash=args.value_hash,
        config=dict(args.config),
    )


async def _replace_artifacts(
    db: AsyncSession, challenge: Challenge, manifest: ChallengeManifest
) -> None:
    await db.execute(
        delete(ChallengeArtifact).where(
            ChallengeArtifact.challenge_id == challenge.id
        )
    )
    await db.flush()
    for artifact in manifest.artifacts:
        db.add(
            ChallengeArtifact(
                challenge_id=challenge.id,
                path=artifact.path,
                sha256=artifact.sha256,
                size_bytes=artifact.size_bytes,
                description=artifact.description,
            )
        )
