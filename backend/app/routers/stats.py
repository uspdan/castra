from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Challenge, Solve, Streak
from app.services.auth import get_current_user, require_admin

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
async def overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    total_challenges_result = await db.execute(
        select(func.count(Challenge.id)).where(
            Challenge.is_released == True, Challenge.is_active == True
        )
    )
    total_challenges = total_challenges_result.scalar()

    total_solves_result = await db.execute(select(func.count(Solve.id)))
    total_solves = total_solves_result.scalar()

    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    active_users_result = await db.execute(
        select(func.count(func.distinct(Solve.user_id))).where(
            Solve.solved_at >= one_week_ago
        )
    )
    active_users_this_week = active_users_result.scalar()

    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    total_users = total_users_result.scalar()

    if total_challenges > 0 and total_users > 0:
        avg_completion = round(total_solves / (total_challenges * total_users), 4)
    else:
        avg_completion = 0.0

    most_solved_result = await db.execute(
        select(Challenge.slug, Challenge.title, func.count(Solve.id).label("cnt"))
        .join(Solve, Solve.challenge_id == Challenge.id)
        .where(Challenge.is_active == True)
        .group_by(Challenge.id, Challenge.slug, Challenge.title)
        .order_by(func.count(Solve.id).desc())
        .limit(1)
    )
    most_solved = most_solved_result.first()

    least_solved_result = await db.execute(
        select(Challenge.slug, Challenge.title, func.count(Solve.id).label("cnt"))
        .join(Solve, Solve.challenge_id == Challenge.id, isouter=True)
        .where(Challenge.is_active == True, Challenge.is_released == True)
        .group_by(Challenge.id, Challenge.slug, Challenge.title)
        .order_by(func.count(Solve.id).asc())
        .limit(1)
    )
    least_solved = least_solved_result.first()

    return {
        "total_challenges": total_challenges,
        "total_solves": total_solves,
        "active_users_this_week": active_users_this_week,
        "total_users": total_users,
        "avg_completion": avg_completion,
        "most_solved_challenge": {
            "slug": most_solved.slug,
            "title": most_solved.title,
            "solve_count": most_solved.cnt,
        }
        if most_solved
        else None,
        "least_solved_challenge": {
            "slug": least_solved.slug,
            "title": least_solved.title,
            "solve_count": least_solved.cnt,
        }
        if least_solved
        else None,
    }


@router.get("/mitre")
async def mitre_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    challenges_result = await db.execute(
        select(Challenge).where(
            Challenge.is_active == True, Challenge.is_released == True
        )
    )
    challenges = challenges_result.scalars().all()

    total_users_result = await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    total_users = total_users_result.scalar()

    technique_challenges: dict[str, list[int]] = {}
    for c in challenges:
        techniques = c.mitre_techniques if c.mitre_techniques else []
        for tech in techniques:
            if tech not in technique_challenges:
                technique_challenges[tech] = []
            technique_challenges[tech].append(c.id)

    results = []
    for technique_id, challenge_ids in technique_challenges.items():
        if total_users > 0:
            users_solved_result = await db.execute(
                select(func.count(func.distinct(Solve.user_id))).where(
                    Solve.challenge_id.in_(challenge_ids)
                )
            )
            users_solved = users_solved_result.scalar()
            solve_percentage = round((users_solved / total_users) * 100, 2)
        else:
            solve_percentage = 0.0

        results.append(
            {
                "technique_id": technique_id,
                "challenge_count": len(challenge_ids),
                "solve_percentage": solve_percentage,
            }
        )

    results.sort(key=lambda x: x["technique_id"])
    return results


@router.get("/activity")
async def activity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    four_weeks_ago = datetime.now(timezone.utc) - timedelta(weeks=4)

    solve_data_result = await db.execute(
        select(
            cast(Solve.solved_at, Date).label("solve_date"),
            Challenge.team,
            func.count(Solve.id).label("cnt"),
        )
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .where(Solve.solved_at >= four_weeks_ago)
        .group_by(cast(Solve.solved_at, Date), Challenge.team)
        .order_by(cast(Solve.solved_at, Date))
    )
    rows = solve_data_result.all()

    date_map: dict[str, dict[str, int]] = {}
    for row in rows:
        date_str = str(row.solve_date)
        if date_str not in date_map:
            date_map[date_str] = {"red_solves": 0, "blue_solves": 0}
        if row.team == "red":
            date_map[date_str]["red_solves"] = row.cnt
        elif row.team == "blue":
            date_map[date_str]["blue_solves"] = row.cnt

    activity_list = [
        {"date": date, "red_solves": data["red_solves"], "blue_solves": data["blue_solves"]}
        for date, data in sorted(date_map.items())
    ]

    return activity_list


@router.get("/user/{user_id}")
async def user_stats(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.id != user_id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied.")

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    solves_by_category_result = await db.execute(
        select(Challenge.category, func.count(Solve.id).label("cnt"))
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .where(Solve.user_id == user_id)
        .group_by(Challenge.category)
    )
    solves_by_category = [
        {"category": row.category, "solve_count": row.cnt}
        for row in solves_by_category_result.all()
    ]

    all_challenges_result = await db.execute(
        select(Challenge).where(
            Challenge.is_active == True, Challenge.is_released == True
        )
    )
    all_challenges = all_challenges_result.scalars().all()

    user_solved_ids_result = await db.execute(
        select(Solve.challenge_id).where(Solve.user_id == user_id)
    )
    user_solved_ids = set(user_solved_ids_result.scalars().all())

    skill_counts: dict[str, dict[str, int]] = {}
    for c in all_challenges:
        skills = c.skills if c.skills else []
        for skill in skills:
            if skill not in skill_counts:
                skill_counts[skill] = {"total": 0, "solved": 0}
            skill_counts[skill]["total"] += 1
            if c.id in user_solved_ids:
                skill_counts[skill]["solved"] += 1

    skill_percentages = [
        {
            "skill": skill,
            "solved": data["solved"],
            "total": data["total"],
            "percentage": round((data["solved"] / data["total"]) * 100, 2)
            if data["total"] > 0
            else 0.0,
        }
        for skill, data in sorted(skill_counts.items())
    ]

    technique_counts: dict[str, dict[str, int]] = {}
    for c in all_challenges:
        techniques = c.mitre_techniques if c.mitre_techniques else []
        for tech in techniques:
            if tech not in technique_counts:
                technique_counts[tech] = {"total": 0, "solved": 0}
            technique_counts[tech]["total"] += 1
            if c.id in user_solved_ids:
                technique_counts[tech]["solved"] += 1

    mitre_coverage = [
        {
            "technique_id": tech,
            "solved": data["solved"],
            "total": data["total"],
            "percentage": round((data["solved"] / data["total"]) * 100, 2)
            if data["total"] > 0
            else 0.0,
        }
        for tech, data in sorted(technique_counts.items())
    ]

    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user_id)
    )
    streak_row = streak_result.scalars().first()

    return {
        "user_id": user_id,
        "username": user.username,
        "display_name": user.display_name,
        "solves_by_category": solves_by_category,
        "skill_percentages": skill_percentages,
        "mitre_coverage": mitre_coverage,
        "streak": {
            "current_streak": streak_row.current_streak if streak_row else 0,
            "longest_streak": streak_row.longest_streak if streak_row else 0,
            "last_solve_date": str(streak_row.last_solve_date) if streak_row and streak_row.last_solve_date else None,
        },
    }
