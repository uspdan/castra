"""Read-side challenge aggregations.

Extracted from ``routers/challenges.py`` in Phase 6. The list and detail
endpoints each fan out to several queries (solve counts, first-blood
display name, hint unlock state, top solvers, prerequisite progress,
write-up counts). Holding all of that in the router put both handlers
well over the 50-line cap.

These helpers are pure read functions: no commits, no side effects.

Phase 12 will lock the response shapes down with explicit DTOs; until
then the dict shapes here mirror what the existing frontend expects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Challenge, HintUnlock, Solve, User, Writeup


@dataclass(frozen=True)
class ListFilters:
    team: Optional[str] = None
    category: Optional[str] = None
    difficulty: Optional[str] = None
    search: Optional[str] = None
    mitre: Optional[str] = None
    sort: str = "newest"
    page: int = 1
    per_page: int = 20


def _apply_filters(stmt, f: ListFilters):
    if f.team:
        stmt = stmt.where(Challenge.team == f.team)
    if f.category:
        stmt = stmt.where(Challenge.category == f.category)
    if f.difficulty:
        stmt = stmt.where(Challenge.difficulty == f.difficulty)
    if f.search:
        pattern = f"%{f.search}%"
        stmt = stmt.where(
            (Challenge.title.ilike(pattern)) | (Challenge.description.ilike(pattern))
        )
    if f.mitre:
        stmt = stmt.where(Challenge.mitre_techniques.cast(str).contains(f.mitre))
    return stmt


def _apply_sort(stmt, sort: str):
    if sort == "points":
        return stmt.order_by(Challenge.points.desc())
    if sort == "difficulty":
        return stmt.order_by(Challenge.difficulty)
    if sort == "solves":
        solve_count_sub = (
            select(func.count(Solve.id))
            .where(Solve.challenge_id == Challenge.id)
            .correlate(Challenge)
            .scalar_subquery()
        )
        return stmt.order_by(solve_count_sub.desc())
    return stmt.order_by(Challenge.created_at.desc())


async def list_challenges(
    *, viewer: User, filters: ListFilters, db: AsyncSession
) -> dict[str, Any]:
    stmt = select(Challenge).where(
        Challenge.is_released.is_(True),
        Challenge.is_active.is_(True),
    )
    stmt = _apply_filters(stmt, filters)
    stmt = _apply_sort(stmt, filters.sort)

    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar()

    page_stmt = stmt.offset((filters.page - 1) * filters.per_page).limit(filters.per_page)
    challenges = (await db.execute(page_stmt)).scalars().all()

    items = []
    for c in challenges:
        items.append(await _list_item(c, viewer, db))
    return {
        "items": items,
        "total": total,
        "page": filters.page,
        "per_page": filters.per_page,
    }


async def _list_item(c: Challenge, viewer: User, db: AsyncSession) -> dict[str, Any]:
    solve_count = (
        await db.execute(
            select(func.count(Solve.id)).where(Solve.challenge_id == c.id)
        )
    ).scalar()

    user_solved = (
        await db.execute(
            select(
                exists().where(
                    and_(Solve.challenge_id == c.id, Solve.user_id == viewer.id)
                )
            )
        )
    ).scalar()

    first_blood_user = (
        await db.execute(
            select(User.display_name)
            .join(Solve, Solve.user_id == User.id)
            .where(Solve.challenge_id == c.id)
            .order_by(Solve.solved_at.asc())
            .limit(1)
        )
    ).scalar()

    return {
        "id": c.id,
        "slug": c.slug,
        "title": c.title,
        "category": c.category,
        "difficulty": c.difficulty,
        "points": c.points,
        "team": c.team,
        "solve_count": solve_count,
        "user_solved": user_solved,
        "first_blood_user": first_blood_user,
        "released_at": str(c.released_at) if c.released_at else None,
    }


async def _solve_count(challenge_id: int, db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count(Solve.id)).where(Solve.challenge_id == challenge_id)
        )
    ).scalar()


async def _viewer_has_solved(challenge_id: int, viewer_id: int, db: AsyncSession) -> bool:
    return bool(
        (
            await db.execute(
                select(
                    exists().where(
                        and_(
                            Solve.challenge_id == challenge_id,
                            Solve.user_id == viewer_id,
                        )
                    )
                )
            )
        ).scalar()
    )


async def _hint_state(
    challenge: Challenge, viewer_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    unlocked = set(
        (
            await db.execute(
                select(HintUnlock.hint_index).where(
                    HintUnlock.user_id == viewer_id,
                    HintUnlock.challenge_id == challenge.id,
                )
            )
        )
        .scalars()
        .all()
    )
    return [
        {"index": i, "text": hint, "locked": False}
        if i in unlocked
        else {"index": i, "text": "{locked}", "locked": True}
        for i, hint in enumerate(challenge.hints or [])
    ]


async def _top_solvers(challenge_id: int, db: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        await db.execute(
            select(
                User.display_name, User.username, Solve.solved_at, Solve.points_awarded
            )
            .join(User, Solve.user_id == User.id)
            .where(Solve.challenge_id == challenge_id)
            .order_by(Solve.solved_at.asc())
            .limit(5)
        )
    ).all()
    return [
        {
            "display_name": r.display_name,
            "username": r.username,
            "solved_at": str(r.solved_at),
            "points_awarded": r.points_awarded,
        }
        for r in rows
    ]


async def _prerequisite_progress(
    challenge: Challenge, viewer_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for prereq_id in challenge.prerequisite_ids or []:
        prereq = (
            await db.execute(
                select(Challenge.slug, Challenge.title).where(
                    Challenge.id == prereq_id
                )
            )
        ).first()
        if not prereq:
            continue
        out.append(
            {
                "slug": prereq.slug,
                "title": prereq.title,
                "user_completed": await _viewer_has_solved(prereq_id, viewer_id, db),
            }
        )
    return out


async def _approved_writeup_count(challenge_id: int, db: AsyncSession) -> int:
    return (
        await db.execute(
            select(func.count(Writeup.id)).where(
                Writeup.challenge_id == challenge_id,
                Writeup.is_approved.is_(True),
            )
        )
    ).scalar()


async def get_challenge_detail(
    *, slug: str, viewer: User, db: AsyncSession
) -> Optional[dict[str, Any]]:
    """Return the detail dict for a slug, or ``None`` if not found / inactive.

    Caller is responsible for translating ``None`` to a 404.
    """

    challenge = (
        await db.execute(
            select(Challenge).where(
                Challenge.slug == slug, Challenge.is_active.is_(True)
            )
        )
    ).scalars().first()
    if not challenge:
        return None

    return {
        "id": challenge.id,
        "slug": challenge.slug,
        "title": challenge.title,
        "description": challenge.description,
        "category": challenge.category,
        "difficulty": challenge.difficulty,
        "points": challenge.points,
        "team": challenge.team,
        "skills": challenge.skills,
        "mitre_techniques": challenge.mitre_techniques,
        "hints": await _hint_state(challenge, viewer.id, db),
        "solve_count": await _solve_count(challenge.id, db),
        "user_solved": await _viewer_has_solved(challenge.id, viewer.id, db),
        "top_5_solvers": await _top_solvers(challenge.id, db),
        "prerequisites": await _prerequisite_progress(challenge, viewer.id, db),
        "writeup_count": await _approved_writeup_count(challenge.id, db),
        "released_at": str(challenge.released_at) if challenge.released_at else None,
        "created_at": str(challenge.created_at) if challenge.created_at else None,
    }
