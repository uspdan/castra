import json
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from jinja2 import Environment, FileSystemLoader

from app.database import get_db
from app.models import AuditLedger, Challenge, Solve, Streak, User
from app.schemas import UserUpdate
from app.services.auth import require_admin
from app.validators.exact import hash_exact_value

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(select(func.count(User.id)))
    total = total_result.scalar()

    result = await db.execute(
        select(User)
        .order_by(User.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    users = result.scalars().all()

    items = []
    for user in users:
        points_result = await db.execute(
            select(func.coalesce(func.sum(Solve.points_awarded), 0)).where(
                Solve.user_id == user.id
            )
        )
        total_points = points_result.scalar()

        solves_result = await db.execute(
            select(func.count(Solve.id)).where(Solve.user_id == user.id)
        )
        solve_count = solves_result.scalar()

        streak_result = await db.execute(
            select(Streak).where(Streak.user_id == user.id)
        )
        streak_row = streak_result.scalars().first()
        current_streak = streak_row.current_streak if streak_row else 0

        items.append(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "display_name": user.display_name,
                "team": user.team,
                "role": user.role,
                "is_active": user.is_active,
                "total_points": total_points,
                "solve_count": solve_count,
                "current_streak": current_streak,
                "last_login": str(user.last_login) if user.last_login else None,
                "created_at": str(user.created_at) if user.created_at else None,
            }
        )

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    data: UserUpdate,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "detail": "User updated.",
    }


@router.get("/audit")
async def audit_log(
    user_id: int | None = Query(None),
    action: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Read the hash-chained audit ledger.

    Phase 12 (slice 8): the legacy ``audit_logs`` table is gone;
    every state-changing event flows through ``audit_ledger``
    (Phase 2) instead. The response shape is preserved for back-
    compat — ``user_id``/``action``/``details`` fields are derived
    from the ledger row's ``actor_id``/``event_type``/``payload``.
    """

    stmt = select(AuditLedger)

    if user_id is not None:
        stmt = stmt.where(
            AuditLedger.actor_type == "user",
            AuditLedger.actor_id == str(user_id),
        )
    if action:
        stmt = stmt.where(AuditLedger.event_type == action)
    if date_from:
        dt_from = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        stmt = stmt.where(AuditLedger.created_at >= dt_from)
    if date_to:
        dt_to = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
        stmt = stmt.where(AuditLedger.created_at <= dt_to)

    total_result = await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = total_result.scalar()

    stmt = stmt.order_by(AuditLedger.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    items = [
        {
            "id": row.seq,
            "user_id": (
                int(row.actor_id)
                if row.actor_type == "user" and row.actor_id and row.actor_id.isdigit()
                else None
            ),
            "action": row.event_type,
            "details": row.payload,
            "created_at": str(row.created_at) if row.created_at else None,
        }
        for row in rows
    ]

    return {"items": items, "total": total, "page": page, "per_page": per_page}


@router.post("/seed")
async def seed_challenges(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    challenges_dir = Path("/challenges")
    created = 0
    skipped = 0

    if not challenges_dir.exists():
        raise HTTPException(
            status_code=400, detail="Challenges directory not found at /challenges."
        )

    for challenge_dir in sorted(challenges_dir.iterdir()):
        if not challenge_dir.is_dir():
            continue

        challenge_file = challenge_dir / "challenge.json"
        if not challenge_file.exists():
            continue

        with open(challenge_file) as f:
            data = json.load(f)

        slug = data.get("slug", challenge_dir.name)

        existing = await db.execute(
            select(Challenge).where(Challenge.slug == slug)
        )
        if existing.scalars().first():
            skipped += 1
            continue

        flag = data.get("flag", "")
        flag_hashed = hash_exact_value(flag) if flag else ""

        challenge = Challenge(
            slug=slug,
            title=data.get("title", slug),
            description=data.get("description", ""),
            category=data.get("category", "general"),
            difficulty=data.get("difficulty", "easy"),
            points=data.get("points", 100),
            team=data.get("team", "red"),
            flag_hash=flag_hashed,
            hints=data.get("hints", []),
            skills=data.get("skills", []),
            mitre_techniques=data.get("mitre_techniques", []),
            prerequisite_ids=data.get("prerequisite_ids", []),
            is_released=True,
            is_active=True,
            released_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(challenge)
        created += 1

    await db.commit()

    return {"created": created, "skipped": skipped}


@router.get("/system")
async def system_info(
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user_count_result = await db.execute(select(func.count(User.id)))
    user_count = user_count_result.scalar()

    challenge_count_result = await db.execute(select(func.count(Challenge.id)))
    challenge_count = challenge_count_result.scalar()

    solve_count_result = await db.execute(select(func.count(Solve.id)))
    solve_count = solve_count_result.scalar()

    audit_count_result = await db.execute(select(func.count(AuditLedger.seq)))
    audit_count = audit_count_result.scalar()

    container_count = 0
    try:
        import docker

        client = docker.from_env()
        containers = client.containers.list()
        container_count = len(containers)
    except Exception:
        container_count = -1

    return {
        "db_tables": {
            "users": user_count,
            "challenges": challenge_count,
            "solves": solve_count,
            "audit_ledger": audit_count,
        },
        "containers": {
            "running": container_count,
        },
        "version": "2.4.1",
    }


@router.get("/reports/operator/{user_id}")
async def operator_report(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    points_result = await db.execute(
        select(func.coalesce(func.sum(Solve.points_awarded), 0)).where(
            Solve.user_id == user_id
        )
    )
    total_points = points_result.scalar()

    solves_result = await db.execute(
        select(
            Challenge.category,
            Challenge.title,
            Challenge.difficulty,
            Solve.points_awarded,
            Solve.solved_at,
            Solve.is_first_blood,
        )
        .join(Challenge, Solve.challenge_id == Challenge.id)
        .where(Solve.user_id == user_id)
        .order_by(Solve.solved_at.desc())
    )
    solves = solves_result.all()

    solves_by_category: dict[str, int] = {}
    for s in solves:
        solves_by_category[s.category] = solves_by_category.get(s.category, 0) + 1

    streak_result = await db.execute(
        select(Streak).where(Streak.user_id == user_id)
    )
    streak_row = streak_result.scalars().first()

    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))

    try:
        template = env.get_template("reports/operator_report.html")
    except Exception:
        raise HTTPException(
            status_code=500, detail="Report template not found."
        )

    html_content = template.render(
        user=user,
        total_points=total_points,
        total_solves=len(solves),
        solves=solves,
        solves_by_category=solves_by_category,
        current_streak=streak_row.current_streak if streak_row else 0,
        longest_streak=streak_row.longest_streak if streak_row else 0,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    from weasyprint import HTML

    pdf_bytes = HTML(string=html_content).write_pdf()
    buffer = BytesIO(pdf_bytes)
    buffer.seek(0)

    filename = f"operator_report_{user.username}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf"

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
