"""``GET /api/v1/challenges/{slug}/artifacts`` — artifact download.

ADR 005. Artifact-only challenges have no container; their content is
the declared artifact files, served from the read-only challenges mount.
Container-backed challenges may also declare artifacts (pcaps, memory
dumps) and get the same download surface.

Security model, in order of the checks below:

1. Auth — same ``get_current_user`` dependency as every player route.
2. Challenge gating — released + active, same visibility rule as the
   catalogue. An unreleased challenge's artifacts are 404, not 403, so
   the endpoint does not leak which slugs exist.
3. **DB allowlist** — the path must be a ``challenge_artifacts`` row
   for this challenge. Those rows are written by the loader after it
   verified each file's sha256 on disk. Anything else in the tree —
   including the ``.flag.txt`` / ``.answers.json`` sidecars that sit
   next to challenge Dockerfiles — is unreachable regardless of
   whether the file exists.
4. **Containment** — the resolved (symlink-followed) path must land
   inside the challenge's own directory under ``CHALLENGES_DIR``.
   Defence in depth behind the allowlist: even a poisoned DB row
   cannot walk out of the tree.

Files are hash-verified at load time, not per request — hashing a
multi-GiB artifact on every download is an easy CPU DoS (see ADR 005
for the trade-off).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.middleware.rate_limit import general_rate_limit
from app.models import Challenge, ChallengeArtifact, User
from app.services.auth import get_current_user

router = APIRouter()


async def _visible_challenge(slug: str, db: AsyncSession) -> Challenge:
    challenge = (
        await db.execute(
            select(Challenge).where(
                Challenge.slug == slug,
                Challenge.is_active.is_(True),
                Challenge.is_released.is_(True),
            )
        )
    ).scalars().first()
    if challenge is None:
        raise HTTPException(status_code=404, detail="Challenge not found.")
    return challenge


@router.get("/challenges/{slug}/artifacts")
async def list_artifacts(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(general_rate_limit),
) -> dict:
    challenge = await _visible_challenge(slug, db)
    rows = (
        await db.execute(
            select(ChallengeArtifact).where(
                ChallengeArtifact.challenge_id == challenge.id
            ).order_by(ChallengeArtifact.path)
        )
    ).scalars().all()
    return {
        "slug": slug,
        "artifacts": [
            {
                "path": row.path,
                "sha256": row.sha256,
                "size_bytes": row.size_bytes,
                "description": row.description,
            }
            for row in rows
        ],
    }


@router.get("/challenges/{slug}/artifacts/{artifact_path:path}")
async def download_artifact(
    slug: str,
    artifact_path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rl=Depends(general_rate_limit),
) -> FileResponse:
    challenge = await _visible_challenge(slug, db)

    # Allowlist: exact match against the loader-written rows. No
    # normalisation before the lookup — the manifest declared a literal
    # relative path, and that literal string is the only key we honour.
    row = (
        await db.execute(
            select(ChallengeArtifact).where(
                ChallengeArtifact.challenge_id == challenge.id,
                ChallengeArtifact.path == artifact_path,
            )
        )
    ).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="No such artifact.")

    base = (Path(get_settings().CHALLENGES_DIR) / slug).resolve()
    target = (base / row.path).resolve()

    # Containment: the resolved path must stay inside this challenge's
    # directory. Catches `..` in a poisoned DB row and symlinks that
    # point out of the tree. `is_relative_to` follows the resolve()
    # above, so both are covered by one check.
    if not target.is_relative_to(base):
        raise HTTPException(status_code=404, detail="No such artifact.")

    if not target.is_file():
        # Listed in the DB but missing on disk — a deploy that forgot
        # to sync the challenges tree. 503 (not 404): the artifact
        # exists as far as the catalogue is concerned; the server is
        # the thing that is wrong.
        raise HTTPException(
            status_code=503,
            detail="Artifact temporarily unavailable on this deployment.",
        )

    return FileResponse(
        path=target,
        filename=Path(row.path).name,
        media_type="application/octet-stream",
    )
