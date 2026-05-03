"""Challenges router package.

Phase 6 split the original 600-line ``routers/challenges.py`` into three
focused submodules — ``browse`` (read-side), ``engagement`` (user
actions: submit / hint / feedback), and ``admin`` (CRUD) — wired here
into a single ``APIRouter`` so callers keep the existing import shape:

    from app.routers.challenges import router

Each submodule's ``router`` is registered without a path prefix; this
parent owns the ``/challenges`` prefix and the OpenAPI tag.
"""

from fastapi import APIRouter

from app.routers.challenges import admin, browse, engagement

router = APIRouter(prefix="/challenges", tags=["challenges"])
router.include_router(browse.router)
router.include_router(engagement.router)
router.include_router(admin.router)

__all__ = ["router"]
