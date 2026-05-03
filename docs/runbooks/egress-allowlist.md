# Egress allowlist hot-reload

The `egress-proxied` container profile (Phase 9) routes outbound
traffic through `siege-egress-proxy` (tinyproxy) with `FilterDefaultDeny
Yes`. The active allowlist is the union of every active instance's
`manifest.container.egress_allowlist` entries, rendered atomically
into a tinyproxy filter file by
`app.services.orchestration.egress.render_to_file`. After a write,
the api signals the proxy with `SIGHUP` so tinyproxy re-reads the
file without a restart.

## How the pipeline is wired

The api process and `siege-egress-proxy` share a docker volume
(`egress_filter`) mounted at `/srv/egress` in both containers. The api
writes to `/srv/egress/egress-allowlist.conf`; tinyproxy is configured
to read the same path (`docker/egress-proxy/tinyproxy.conf`,
`Filter "/srv/egress/egress-allowlist.conf"`).

Cold-start safety: the proxy entrypoint
(`docker/egress-proxy/entrypoint.sh`) `touch`es the file if missing
before starting tinyproxy. With `FilterDefaultDeny Yes`, an empty
file means "deny everything" — the safe default until the api
writes the first rendered allowlist.

The `EGRESS_FILTER_PATH` env var on the api service points at the
shared path:

```yaml
api:
  environment:
    - EGRESS_FILTER_PATH=/srv/egress/egress-allowlist.conf
  volumes:
    - egress_filter:/srv/egress

egress-proxy:
  volumes:
    - egress_filter:/srv/egress
```

## When does the allowlist refresh?

Automatically on instance lifecycle events that involve an
`egress-proxied` profile:

- `launch_instance` (after the container is up)
- `cleanup_expired` (scheduler sweep)
- `stop_instance` (DELETE /instances/{id})

The signal step is best-effort: a failed `SIGHUP` or render write
never blocks the orchestration flow. Failures are logged at `WARN`
via structlog (`event=egress proxy reload failed`).

## Manual refresh / debug

Render the allowlist on demand without touching docker:

```bash
docker compose exec api python -m app.tools.render_egress_allowlist --json
```

Force a tinyproxy reload:

```bash
docker compose exec docker-proxy /bin/sh -c \
  "wget -qO- --post-data='' http://localhost:2375/containers/siege-egress-proxy/kill?signal=SIGHUP"
```

(Or, with sufficient privileges, `docker kill --signal=SIGHUP
siege-egress-proxy`.)

Inspect the active allowlist:

```bash
docker compose exec egress-proxy cat /srv/egress/egress-allowlist.conf
```

Tail tinyproxy logs:

```bash
docker compose logs -f egress-proxy
```

## Failure modes

- **Tinyproxy `Could not open filter file`** — the entrypoint should
  prevent this. If you see it, the volume is misconfigured or the
  api process can't write to `/srv/egress/`. `docker compose exec
  api ls -la /srv/egress` and confirm the api uid has write access.

- **Allowlist refreshes but instances still blocked** — confirm the
  proxy actually received the SIGHUP: `docker compose logs egress-proxy
  | grep -i hup`. If not, the docker-socket-proxy ACL is missing
  `CONTAINERS=1` + `POST=1` (Phase 9 default).

- **Allowlist refreshes too aggressively** — the dispatch path in
  `refresh_proxy_allowlist` already short-circuits when no
  egress-proxied instances are active (renders an empty file). If
  you see thrashing, the cleanup scheduler interval is the lever.

## Rollback

If the hot-reload pipeline breaks deployment:

1. Drop back to the static allowlist by reverting
   `docker/egress-proxy/tinyproxy.conf` to
   `Filter "/etc/tinyproxy/egress-allowlist.conf"` (the baked-in copy).
2. Comment out the `egress_filter` volume mounts on api +
   egress-proxy.
3. Rebuild egress-proxy (`docker compose build egress-proxy`) and
   restart.
4. The platform falls back to the file shipped in the image; the api
   will continue calling `refresh_proxy_allowlist` and hitting a
   harmless write to a path the proxy ignores.

This rollback path is documented because the static-allowlist mode
is what shipped through Phase 9 and is the known-good baseline.
