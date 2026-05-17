"""Public API v1 — locked-contract surface.

Phase 12 (slice 1) shipped the read endpoints; slice 2 added the two
write endpoints the front-door migration depends on:

- ``GET  /api/v1/challenges``               — paged catalogue
- ``GET  /api/v1/challenges/{slug}``        — challenge detail
- ``GET  /api/v1/scoreboard``               — ranked active users
- ``GET  /api/v1/attack-coverage``          — ATT&CK technique roll-up
- ``GET  /api/v1/me``                       — current user + totals + rank
- ``POST /api/v1/challenges/{slug}/submit``   — flag submission (slice 2)
- ``POST /api/v1/challenges/{slug}/hint``     — unlock next hint (slice 2)
- ``GET  /api/v1/challenges/{slug}/progress`` — per-flag progress (slice 3)
- ``POST/GET/DELETE /api/v1/webhooks`` — admin webhook CRUD (slice 5)

Every response is a pydantic ``BaseModel`` with
``ConfigDict(extra="forbid")`` so internal columns can't leak. The
legacy non-versioned routes stay live alongside this surface until
the frontend cuts over.
"""

from fastapi import APIRouter

from . import (
    admin,
    attack_coverage,
    auth,
    challenges,
    hints,
    leaderboard,
    me,
    progress,
    scoreboard,
    submit,
    webhooks,
    workstation,
)

router = APIRouter(prefix="/api/v1", tags=["v1"])
router.include_router(auth.router)
router.include_router(admin.router)
router.include_router(challenges.router)
router.include_router(scoreboard.router)
router.include_router(leaderboard.router)
router.include_router(attack_coverage.router)
router.include_router(me.router)
router.include_router(submit.router)
router.include_router(hints.router)
router.include_router(progress.router)
router.include_router(webhooks.router)
router.include_router(workstation.router)

__all__ = ["router"]
