"""``GET /api/v1/attack-coverage`` — per-technique roll-up."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.v1.coverage import AttackCoverageEntry, AttackCoverageResponse
from app.services.api_v1 import compute_attack_coverage
from app.services.auth import get_current_user

router = APIRouter()


@router.get("/attack-coverage", response_model=AttackCoverageResponse)
async def attack_coverage_v1(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttackCoverageResponse:
    entries, total_techniques, total_challenges = await compute_attack_coverage(
        db, viewer_id=current_user.id
    )
    return AttackCoverageResponse(
        entries=[
            AttackCoverageEntry(
                technique_id=tech,
                challenge_count=count,
                solved_by_viewer=solved,
            )
            for tech, count, solved in entries
        ],
        total_techniques=total_techniques,
        total_challenges=total_challenges,
    )
