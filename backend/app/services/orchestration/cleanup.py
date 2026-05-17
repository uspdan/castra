"""Stop/cleanup helpers for the orchestrator.

Same-transaction guarantee: ``stop_instance`` and ``cleanup_expired``
flush DB writes but never commit. The caller's surrounding transaction
commits the audit row alongside the business write (see Phase 9 plan).
"""

from __future__ import annotations

from datetime import datetime, timezone

import docker
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChallengeInstance, InstanceStatus
from app.services.audit import ActorType, EventType, append as audit_append
from app.services.orchestration import docker_client, networking

logger = structlog.get_logger()


async def stop_instance(instance_id: int, db: AsyncSession, redis_client) -> None:
    """Stop a running instance, tear down its bridge, mark it stopped.

    ``redis_client`` is unused today but retained for parity with the
    legacy signature; future port-recycling lives here.
    """
    del redis_client  # reserved
    result = await db.execute(
        select(ChallengeInstance).where(ChallengeInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise ValueError("Instance not found")

    client = docker_client.get()
    _stop_container(client, instance.container_id)

    # Phase 12 follow-up: per-instance egress sidecar teardown. The
    # sidecar is attached to the instance's network so it must be
    # removed before the network is torn down.
    if instance.sidecar_container_id:
        from app.services.orchestration import sidecar as sidecar_mod

        sidecar_mod.teardown_sidecar(client, instance.sidecar_container_id)

    if instance.network_name:
        networking.remove_network(client, instance.network_name)

    was_egress_proxied = instance.applied_profile == "egress-proxied"
    instance.status = InstanceStatus.stopped
    instance.stopped_at = datetime.now(timezone.utc)
    await db.flush()

    # Phase 12 (slice 17): teardown of an egress-proxied instance
    # requires re-rendering the proxy's allowlist (the stopped
    # instance's FQDNs may now be the only thing keeping a rule
    # alive). Same best-effort discipline as launch. Sidecar-mode
    # instances are isolated by construction so the shared proxy's
    # allowlist is unaffected.
    if was_egress_proxied:
        from app.services.orchestration.egress import refresh_proxy_allowlist

        await refresh_proxy_allowlist(db, client)


def _stop_container(client: docker.DockerClient, container_id: str | None) -> None:
    if not container_id:
        return
    try:
        container = client.containers.get(container_id)
    except docker.errors.NotFound:
        return
    try:
        container.stop(timeout=5)
    except docker.errors.APIError as exc:
        logger.warning("container.stop_failed", id=container_id, error=str(exc))
    try:
        container.remove(force=True)
    except docker.errors.APIError as exc:
        logger.warning("container.remove_failed", id=container_id, error=str(exc))


async def cleanup_expired(db: AsyncSession, redis_client) -> int:
    """TTL reaper: stop expired instances, audit each in same tx."""
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(ChallengeInstance).where(
            ChallengeInstance.status == InstanceStatus.running,
            ChallengeInstance.expires_at < now,
        )
    )
    expired = result.scalars().all()
    count = 0
    for instance in expired:
        try:
            await stop_instance(instance.id, db, redis_client)
            await audit_append(
                db,
                event_type=EventType.INSTANCE_EXPIRED,
                actor_type=ActorType.SYSTEM,
                actor_id="scheduler.ttl_reaper",
                resource_type="instance",
                resource_id=instance.id,
                payload={
                    "instance_id": instance.id,
                    "user_id": instance.user_id,
                    "challenge_id": instance.challenge_id,
                    "applied_profile": instance.applied_profile,
                    "expired_at": (
                        instance.expires_at.isoformat()
                        if instance.expires_at
                        else None
                    ),
                },
            )
            await db.commit()
            count += 1
            logger.info("instance.cleanup", instance_id=instance.id)
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.error(
                "instance.cleanup_failed",
                instance_id=instance.id,
                error=str(exc),
            )
    return count


async def sweep_orphaned_instances(db: AsyncSession) -> int:
    """Reconciliation sweep: mark any ``running`` ``ChallengeInstance``
    whose container is gone from the daemon as ``expired``.

    Runs at API startup (recovers from an orchestrator/DinD recreate
    that wiped containers but left DB rows behind) and on the
    cleanup-watcher's interval as a belt-and-braces. Cheap — one
    ``docker.containers.list()`` plus one SELECT.
    """
    from app.services.orchestration import docker_client

    result = await db.execute(
        select(ChallengeInstance).where(
            ChallengeInstance.status == InstanceStatus.running,
        )
    )
    rows = list(result.scalars().all())
    if not rows:
        return 0

    try:
        client = docker_client.get()
        live = {c.id for c in client.containers.list(all=True)}
        live_short = {cid[:12] for cid in live}
    except Exception as exc:  # noqa: BLE001
        logger.warning("orphan_sweep.docker_list_failed", error=str(exc))
        return 0

    swept = 0
    for inst in rows:
        cid = inst.container_id or ""
        if cid and (cid in live or cid[:12] in live_short):
            continue
        # Container vanished. Mark stopped + audit.
        inst.status = InstanceStatus.stopped
        try:
            await audit_append(
                db,
                event_type=EventType.INSTANCE_EXPIRED,
                actor_type=ActorType.SYSTEM,
                actor_id="scheduler.orphan_sweep",
                resource_type="instance",
                resource_id=inst.id,
                payload={
                    "instance_id": inst.id,
                    "user_id": inst.user_id,
                    "challenge_id": inst.challenge_id,
                    "applied_profile": inst.applied_profile,
                    "reason": "container_gone",
                },
            )
            await db.commit()
            swept += 1
            logger.info("instance.orphan_swept", instance_id=inst.id)
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            logger.warning(
                "instance.orphan_sweep_failed", instance_id=inst.id, error=str(exc)
            )
    return swept


async def get_instance_status(instance_id: int, db: AsyncSession) -> dict:
    """Return per-instance runtime state (used by ws_manager)."""
    result = await db.execute(
        select(ChallengeInstance).where(ChallengeInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if instance is None:
        raise ValueError("Instance not found")

    info = {
        "id": instance.id,
        "status": instance.status.value,
        "container_id": instance.container_id,
        "port": instance.assigned_port,
        "started_at": instance.started_at.isoformat() if instance.started_at else None,
        "expires_at": instance.expires_at.isoformat() if instance.expires_at else None,
        "profile": instance.applied_profile,
    }
    if instance.status == InstanceStatus.running and instance.container_id:
        info.update(_runtime_stats(instance.container_id))
    return info


def _runtime_stats(container_id: str) -> dict:
    try:
        client = docker_client.get()
        container = client.containers.get(container_id)
        stats = container.stats(stream=False)
        return {
            "docker_status": container.status,
            "memory_usage": stats.get("memory_stats", {}).get("usage", 0),
        }
    except Exception:  # noqa: BLE001
        return {"docker_status": "unknown"}


__all__ = ["cleanup_expired", "get_instance_status", "stop_instance"]
