"""Profile-driven container launcher (Phase 9).

Replaces the pre-Phase-9 ``orchestrator.launch_instance`` 116-line
function. Public contract:

    await launch_instance(user_id, challenge, db, redis_client) -> dict

Behaviour:
    * Profile lookup: ``challenge.docker_config["profile"]`` keyed
      against :mod:`app.services.orchestration.profiles`. Unknown
      profile → ``UnknownProfile`` (422 at the router).
    * Digest enforcement: ``challenge.docker_config["digest"]`` must
      be a non-empty ``sha256:<64hex>`` string. Missing →
      ``MissingImageDigest``.
    * Profile fields **override** anything the manifest tried to set
      on a profile-managed field. The launcher composes its docker-py
      kwargs purely from the profile, then runs
      :func:`app.services.orchestration.forbidden.enforce_no_forbidden`
      as a runtime guard.
    * No internal ``db.commit()``: the surrounding router transaction
      commits the ``ChallengeInstance`` insert and the audit row in
      one shot.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import docker
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Challenge, ChallengeInstance, InstanceStatus
from app.security.seccomp import load_profile, profile_sha256
from app.services.orchestration import docker_client, networking, profiles
from app.services.orchestration.forbidden import enforce_no_forbidden

logger = structlog.get_logger()

_LAUNCH_LOCK_TTL_SEC = 30
_MAX_ACTIVE_INSTANCES_PER_USER = 3


def _port_range() -> tuple[int, int]:
    s = get_settings()
    return s.INSTANCE_PORT_MIN, s.INSTANCE_PORT_MAX


class MissingImageDigest(ValueError):
    """Manifest declares no ``container.digest`` — refused at launch."""


class PostPullDigestMismatch(ValueError):
    """The daemon-resolved image's ``RepoDigests`` does not include the
    pinned ``{base}@{digest}`` reference.

    Phase 12 (slice 11) closes the residual TOCTOU window between
    ``docker-py`` resolving an ``image@digest`` reference and the
    container being trusted: after ``containers.run`` returns we
    introspect the resolved image's ``RepoDigests`` and refuse to
    leave a container running unless our pinned reference is
    present. A concurrent daemon-side re-tag (or a tampered local
    cache) producing a different digest no longer slips through.
    """


def _resolve_profile(challenge: Challenge) -> profiles.ContainerProfile:
    name = (challenge.docker_config or {}).get("profile", "default-strict")
    return profiles.get(name)  # raises UnknownProfile on miss


def _resolve_digest(challenge: Challenge) -> str | None:
    digest = (challenge.docker_config or {}).get("digest")
    if digest:
        return digest
    settings = get_settings()
    if settings.REQUIRE_IMAGE_DIGEST:
        raise MissingImageDigest(
            f"challenge {challenge.slug!r} has no container.digest; "
            "Phase 9 refuses to launch un-pinned images"
        )
    # Dev path — caller will skip ``_verify_post_pull_digest`` too.
    return None


def _verify_post_pull_digest(
    container, *, expected_image_ref: str
) -> None:
    """Assert ``RepoDigests`` on the resolved image includes our pin.

    Belt-and-braces guard against any path between the launcher's
    declared ``image@digest`` and the running container that could
    silently substitute different content (concurrent daemon re-tag,
    tampered local cache, etc.). Raises
    :class:`PostPullDigestMismatch` on miss; the caller stops +
    removes the offending container before re-raising to the
    request handler.
    """

    try:
        image = container.image
        attrs = getattr(image, "attrs", None) or {}
        repo_digests = list(attrs.get("RepoDigests") or [])
    except Exception as exc:  # noqa: BLE001 — surface as digest error
        raise PostPullDigestMismatch(
            f"could not introspect container image: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if expected_image_ref not in repo_digests:
        raise PostPullDigestMismatch(
            f"image digest mismatch: expected "
            f"{expected_image_ref!r} in RepoDigests {repo_digests!r}"
        )


def _image_ref(challenge: Challenge, digest: str) -> str:
    base = challenge.docker_image
    if "@" in base:
        return base
    return f"{base}@{digest}"


async def _check_user_caps(db: AsyncSession, user_id: int, challenge: Challenge) -> None:
    active = await db.execute(
        select(func.count(ChallengeInstance.id)).where(
            ChallengeInstance.user_id == user_id,
            ChallengeInstance.status == InstanceStatus.running,
        )
    )
    if (active.scalar() or 0) >= _MAX_ACTIVE_INSTANCES_PER_USER:
        raise ValueError(
            f"Maximum {_MAX_ACTIVE_INSTANCES_PER_USER} active instances allowed"
        )

    existing = await db.execute(
        select(ChallengeInstance).where(
            ChallengeInstance.user_id == user_id,
            ChallengeInstance.challenge_id == challenge.id,
            ChallengeInstance.status == InstanceStatus.running,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError("Instance already running for this challenge")


async def _allocate_port(redis_client) -> int:
    port_min, port_max = _port_range()
    port = await redis_client.incr("siege:next_port")
    if port < port_min or port > port_max:
        await redis_client.set("siege:next_port", port_min)
        port = port_min
    return int(port)


def _resolve_ttl(profile: profiles.ContainerProfile) -> datetime:
    settings = get_settings()
    requested = int(getattr(settings, "CONTAINER_TIMEOUT", 7_200))
    capped = min(requested, profile.ttl_seconds_max)
    return datetime.now(timezone.utc) + timedelta(seconds=capped)


def _build_run_kwargs(
    *,
    profile: profiles.ContainerProfile,
    image_ref: str,
    container_name: str,
    network_name: str,
    challenge: Challenge,
    host_port: int,
    expires_at: datetime,
    digest: str | None,
) -> dict[str, Any]:
    seccomp_json = load_profile(profile.seccomp_profile)
    import json as _json  # local: we only need the dump call here

    security_opt = list(profile.security_opt) + [
        "seccomp=" + _json.dumps(seccomp_json, separators=(",", ":"))
    ]
    return {
        "image": image_ref,
        "name": container_name,
        "detach": True,
        "read_only": profile.read_only,
        "tmpfs": dict(profile.tmpfs),
        "mem_limit": profile.mem_limit,
        "cpu_quota": profile.cpu_quota,
        "cpu_period": profile.cpu_period,
        "pids_limit": profile.pids_limit,
        "security_opt": security_opt,
        "cap_drop": list(profile.cap_drop),
        "cap_add": list(profile.cap_add),
        "network": network_name,
        "ports": {f"{challenge.docker_port}/tcp": host_port},
        "labels": {
            "siege.profile": profile.name,
            "siege.digest": digest or "",
            "siege.slug": challenge.slug,
            "siege.expires": expires_at.isoformat(),
        },
    }


async def launch_instance(
    user_id: int,
    challenge: Challenge,
    db: AsyncSession,
    redis_client,
) -> dict:
    profile = _resolve_profile(challenge)
    digest = _resolve_digest(challenge)
    await _check_user_caps(db, user_id, challenge)

    lock_key = f"siege:lock:{user_id}:{challenge.slug}"
    acquired = await redis_client.set(
        lock_key, "1", nx=True, ex=_LAUNCH_LOCK_TTL_SEC
    )
    if not acquired:
        raise ValueError("Instance launch already in progress")

    try:
        host_port = await _allocate_port(redis_client)
        expires_at = _resolve_ttl(profile)
        container_name = f"siege-{user_id}-{challenge.slug}-{secrets.token_hex(3)}"
        client = docker_client.get()

        # Bridge mode: shared egress-proxy attaches for "egress-proxied";
        # per-instance sidecar mode creates an internal network with NO
        # shared proxy attached — the sidecar is launched separately
        # below and joins this same network.
        share_egress_proxy = profile.network_mode == "egress-proxied"
        sidecar_mode = profile.network_mode == "egress-proxied-sidecar"
        network = networking.create_instance_network(
            client,
            user_id=user_id,
            slug=challenge.slug,
            egress_proxied=share_egress_proxy,
            internal_only=sidecar_mode,
        )

        sidecar_container_id: str | None = None
        if sidecar_mode:
            from app.services.orchestration import sidecar as sidecar_mod

            allowlist = list(
                (challenge.docker_config or {}).get("egress_allowlist") or []
            )
            try:
                launched = sidecar_mod.launch_sidecar(
                    client,
                    network_name=network.name,
                    allowlist=allowlist,
                    instance_label=f"{user_id}-{challenge.slug}",
                )
            except Exception:
                networking.remove_network(client, network.name)
                raise
            sidecar_container_id = launched.container_id

        image_ref = _image_ref(challenge, digest) if digest else challenge.docker_image
        run_kwargs = _build_run_kwargs(
            profile=profile,
            image_ref=image_ref,
            container_name=container_name,
            network_name=network.name,
            challenge=challenge,
            host_port=host_port,
            expires_at=expires_at,
            digest=digest,
        )
        enforce_no_forbidden(run_kwargs)

        # Create+connect+start rather than .run() so we can pin the
        # slug as a network alias *before* the container ever has a
        # network endpoint. This avoids the disconnect-reconnect
        # blip we had with the post-start alias dance.
        target_network = run_kwargs.pop("network", None)
        try:
            container = client.containers.create(**run_kwargs)
            if target_network:
                try:
                    bridge = client.networks.get("bridge")
                    bridge.disconnect(container, force=False)
                except Exception:
                    pass
                client.networks.get(target_network).connect(
                    container, aliases=[challenge.slug]
                )
            container.start()
        except Exception:
            try:
                container.remove(force=True)  # type: ignore[possibly-unbound]
            except Exception:
                pass
            if sidecar_container_id is not None:
                from app.services.orchestration import sidecar as sidecar_mod

                sidecar_mod.teardown_sidecar(client, sidecar_container_id)
            networking.remove_network(client, network.name)
            raise

        # Phase 12 (slice 11): post-pull digest verification. If the
        # daemon resolved an image whose ``RepoDigests`` does not
        # include our pinned ref, kill the container and reject the
        # launch — the caller maps the exception to 409. Skipped when
        # the dev escape hatch (``REQUIRE_IMAGE_DIGEST=false``) is on
        # and the manifest didn't carry a digest in the first place.
        try:
            if digest is not None:
                _verify_post_pull_digest(container, expected_image_ref=image_ref)
        except PostPullDigestMismatch:
            try:
                container.stop(timeout=2)
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001
                pass
            if sidecar_container_id is not None:
                from app.services.orchestration import sidecar as sidecar_mod

                sidecar_mod.teardown_sidecar(client, sidecar_container_id)
            networking.remove_network(client, network.name)
            raise

        # Connect the user's analyst workstation (if running) to
        # the per-instance network so ``ssh <slug>`` resolves from
        # inside the workstation. UX-only — never blocks the
        # launch. Audit-emits ``workstation.attached`` on success.
        try:
            from app.services import workstation as ws
            from app.services.audit import (
                ActorType as _ActorType,
                EventType as _EventType,
                append as _audit_append,
            )

            attached = ws.attach_to_network(
                user_id=user_id, network_name=network.name
            )
            if attached:
                try:
                    await _audit_append(
                        db,
                        event_type=_EventType.WORKSTATION_ATTACHED,
                        actor_type=_ActorType.SYSTEM,
                        actor_id="orchestrator.launcher",
                        resource_type="workstation",
                        resource_id=f"seige-workstation-{user_id}",
                        payload={
                            "container": f"seige-workstation-{user_id}",
                            "network": network.name,
                            "challenge_slug": challenge.slug,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("workstation.attach.audit_failed", error=str(exc))
        except Exception as exc:  # noqa: BLE001
            logger.warning("workstation.attach.skip", error=str(exc))

        instance = ChallengeInstance(
            user_id=user_id,
            challenge_id=challenge.id,
            container_id=container.id,
            container_name=container_name,
            status=InstanceStatus.running,
            assigned_ip="0.0.0.0",
            assigned_port=host_port,
            network_name=network.name,
            started_at=datetime.now(timezone.utc),
            expires_at=expires_at,
            applied_profile=profile.name,
            applied_digest=digest,
            seccomp_profile_sha256=profile_sha256(profile.seccomp_profile),
            sidecar_container_id=sidecar_container_id,
        )
        db.add(instance)
        await db.flush()
        await db.refresh(instance)

        # Phase 12 (slice 17): if this is an egress-proxied instance,
        # the proxy's allowlist must include the new instance's
        # FQDNs. Render the union of all active instances' allowlists
        # and SIGHUP tinyproxy. Best-effort — failures are logged
        # but never block the launch.
        if profile.network_mode == "egress-proxied":
            from app.services.orchestration.egress import (
                refresh_proxy_allowlist,
            )

            await refresh_proxy_allowlist(db, client)

        return {
            "instance_id": instance.id,
            "container_id": container.id,
            "ip": "0.0.0.0",
            "port": host_port,
            "expires_at": expires_at,
            "profile": profile.name,
            "digest": digest,
            "sidecar_container_id": sidecar_container_id,
        }
    finally:
        await redis_client.delete(lock_key)


__all__ = [
    "MissingImageDigest",
    "PostPullDigestMismatch",
    "launch_instance",
]
