"""``POST /api/v1/workstation/launch`` and friends.

Per-player analyst-workstation lifecycle endpoints. See
``app.services.workstation`` for the orchestration mechanics.

State-changing events (launch / stop) are appended to the
hash-chained audit ledger per CLAUDE.md §4. The launcher hook
that attaches a running workstation to a per-instance challenge
network emits ``workstation.attached`` from its call site.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.services import workstation as ws
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.audit.request_context import context_from_request
from app.services.auth import get_current_user

router = APIRouter(prefix="/workstation", tags=["workstation"])


class WorkstationStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    running: bool
    container: str
    ssh_host_port: Optional[int] = None
    web_host_port: Optional[int] = None
    # Player-facing connection strings the frontend renders verbatim.
    # Derived from the request's Host + X-Forwarded-Proto headers so
    # the URLs work behind whatever front-door the player reaches
    # the platform through.
    ssh_command: Optional[str] = None
    web_url: Optional[str] = None


class WorkstationLaunchResponse(WorkstationStatus):
    # One-shot — only set on the launch response, never re-emitted
    # on /status. If the player loses it, they stop + relaunch.
    one_shot_password: Optional[str] = None


def _public_host(request: Request) -> str:
    """Best-effort player-visible host. Falls back to ``localhost``."""
    forwarded = request.headers.get("x-forwarded-host")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    host = request.headers.get("host") or "localhost"
    return host.split(":", 1)[0]


def _public_scheme(request: Request) -> str:
    """Prefer X-Forwarded-Proto so URLs render https behind TLS proxies."""
    fp = request.headers.get("x-forwarded-proto")
    if fp:
        return fp.split(",", 1)[0].strip()
    return request.url.scheme or "http"


def _is_proxied(request: Request) -> bool:
    """True if the request reached the API through nginx (or any
    other front-door that sets the standard X-Forwarded-* headers).
    """
    return bool(
        request.headers.get("x-forwarded-host")
        or request.headers.get("x-forwarded-proto")
    )


def _to_status(
    d: ws.WorkstationDescriptor,
    host: str,
    scheme: str,
    *,
    proxied: bool,
    user_id: int,
) -> dict:
    body: dict = {
        "running": d.running,
        "container": d.container,
        "ssh_host_port": d.ssh_host_port,
        "web_host_port": d.web_host_port,
        "ssh_command": None,
        "web_url": None,
    }
    if d.running and d.ssh_host_port:
        body["ssh_command"] = f"ssh -p {d.ssh_host_port} analyst@{host}"
    if d.running and d.web_host_port:
        if proxied:
            # Path-form proxy URL: nginx matches
            # ``/workstation/<3-digit-user-id>/`` and forwards to
            # ``127.0.0.1:11<id>``. Keeps the URL on-domain behind
            # the platform's TLS + auth posture.
            body["web_url"] = f"{scheme}://{host}/workstation/{user_id:03d}/"
        else:
            body["web_url"] = f"{scheme}://{host}:{d.web_host_port}/"
    return body


@router.get("/status", response_model=WorkstationStatus)
async def workstation_status(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> WorkstationStatus:
    d = ws.get_status(user_id=current_user.id)
    return WorkstationStatus(
        **_to_status(d, _public_host(request), _public_scheme(request), proxied=_is_proxied(request), user_id=current_user.id)
    )


@router.post("/launch", response_model=WorkstationLaunchResponse)
async def workstation_launch(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkstationLaunchResponse:
    try:
        d = ws.launch(user_id=current_user.id)
    except Exception as exc:
        # Most likely "no such image: siege/workstation:latest" if the
        # operator hasn't run `make workstation-build` yet.
        raise HTTPException(status_code=503, detail=f"workstation unavailable: {exc}")

    # Audit only on fresh launches — a re-call against a running
    # workstation is idempotent and returns ``one_shot_password=None``.
    if d.one_shot_password is not None:
        try:
            await audit_append(
                db,
                event_type=EventType.WORKSTATION_LAUNCH,
                actor_type=ActorType.USER,
                actor_id=current_user.id,
                resource_type="workstation",
                resource_id=d.container,
                payload={
                    "container": d.container,
                    "ssh_host_port": d.ssh_host_port,
                    "web_host_port": d.web_host_port,
                },
                **context_from_request(request),
            )
            await db.commit()
        except Exception:
            # Ledger error must NOT roll back a successful workstation
            # launch — log and continue. (CLAUDE.md §4: prefer audit
            # correctness over availability, but never *block* an
            # already-completed side-effect.)
            await db.rollback()

    return WorkstationLaunchResponse(
        **_to_status(
            d,
            _public_host(request),
            _public_scheme(request),
            proxied=_is_proxied(request),
            user_id=current_user.id,
        ),
        one_shot_password=d.one_shot_password,
    )


@router.post("/stop", response_model=WorkstationStatus)
async def workstation_stop(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkstationStatus:
    stopped = ws.stop(user_id=current_user.id)
    d = ws.get_status(user_id=current_user.id)

    if stopped:
        try:
            await audit_append(
                db,
                event_type=EventType.WORKSTATION_STOP,
                actor_type=ActorType.USER,
                actor_id=current_user.id,
                resource_type="workstation",
                resource_id=d.container,
                payload={"container": d.container},
                **context_from_request(request),
            )
            await db.commit()
        except Exception:
            await db.rollback()

    return WorkstationStatus(
        **_to_status(d, _public_host(request), _public_scheme(request), proxied=_is_proxied(request), user_id=current_user.id)
    )
