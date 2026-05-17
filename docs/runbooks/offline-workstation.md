# Offline Workstation — Player Runbook

> When VPN to the central seige-range deployment isn't available
> (customer-site engagement, conference, flight, air-gapped lab),
> every live-shell challenge runs **directly on the player's
> laptop** via Docker. No web UI, no central orchestrator, no
> network egress required after the bundle is loaded.

## Prerequisites

* Docker Engine ≥ 20.10 (Docker Desktop on macOS / Windows; native
  Docker on Linux). `docker info` must work.
* `~/.seige/` writeable (defaults to `$HOME/.seige`; override with
  `SEIGE_STATE`).
* Either:
  * **A.** A full clone of `seige-range` plus internet access to
    Docker Hub for base images (`ubuntu:22.04`, `python:3.12-slim`,
    `node:20-slim`, `php:8.2-apache`).
  * **B.** A pre-built **offline bundle** (`seige-offline-<DATE>.tar.zst`,
    typically 1.5-3 GB depending on which images are included).

Option **A** is what you use at the office. Option **B** is what
you take on the road.

## Option A — playing from the repo (online)

```sh
# 1. Build every challenge image (~10 min cold; cached after).
./scripts/seige pull

# 2. List what's available.
./scripts/seige list

# 3. Start a challenge.
./scripts/seige start windows-dc-live
# -> [seige] up — ssh -p 54392 hunter@127.0.0.1   (password: hunter)

# 4. Open the challenge.
./scripts/seige connect windows-dc-live
# Prints the SSH command. Run it in another terminal. Or:
./scripts/seige connect --exec windows-dc-live
# (docker exec straight into hunter's bash)

# 5. Investigate.  In the SSH session: `connect <device>` to enter
#    the live device CLI; run forensics queries; `exit` back to bash.

# 6. Submit answers.
./scripts/seige answer windows-dc-live 1 "REDACTED"
./scripts/seige answer windows-dc-live 2 "REDACTED"
# ... or `answer remember` inside the SSH session, then `answer reveal`.

# 7. Once every question is right:
./scripts/seige reveal windows-dc-live
# -> {"flag":"CTF{REDACTED}"}

# 8. Wrap up.
./scripts/seige stop windows-dc-live
./scripts/seige score
```

State (started containers, answers, solves, points) is persisted
to `~/.seige/state.json` — interruption-safe and survives reboots.

## Option B — playing from a pre-built bundle (offline / air-gapped)

### Build the bundle (online host, once per release)

```sh
scripts/build-offline-bundle.sh
# -> dist/seige-offline-20260517.tar.zst
```

The bundle contains:
* `images/all.tar` — every `siege/<slug>:latest` image, deduped at
  the layer level by `docker save`.
* `scripts/seige` — the offline player CLI.
* `challenges/<slug>/challenge.json` — manifests so `seige list`
  works without the full repo.
* `load-images.sh` — one-line image loader for the target host.
* `README.md` — this runbook.

### Take it to the target

```sh
# On a USB stick / approved file-transfer mechanism, copy to the
# target laptop. Then:
tar --use-compress-program=unzstd -xvf seige-offline-20260517.tar.zst
cd seige-offline-20260517

# Load images into the local Docker engine.
./load-images.sh
# Loaded image: siege/windows-dc-live:latest
# Loaded image: siege/device-fortigate-live:latest
# ... etc.

# Play.
./scripts/seige list
./scripts/seige start windows-dc-live
./scripts/seige connect --exec windows-dc-live
```

No internet. No VPN. No central seige-range backend. Just Docker
and the bundle.

## What's in scope (and what isn't)

**In scope** — the live-shell challenges that ship as
self-contained images:
* Network-device-forensics live-CLI track (10 vendors).
* Windows / AD forensics track (5 hosts).
* Linux forensics track (1 host).
* Red-team challenges (~22).

**Out of scope** — the central seige-range platform UI and any
scoring leaderboards. The offline CLI tracks one player's solves
locally; it does not sync back to a central instance.

## Bringing solves back online

When VPN access is restored:

```sh
# On the offline laptop:
cat ~/.seige/state.json     # contains solved_at + flag per slug

# On the seige-range UI:
# Submit each flag manually via the player profile -> Submit Flag
# form (one-shot per slug). The platform recognises the same flag
# strings and credits the points.
```

A future iteration may add `seige sync --upstream <URL>` for
batch sync, gated behind authentication. Today the flow is manual.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `docker: command not found` | Install Docker Desktop / Engine. |
| `permission denied` on docker socket (Linux) | Add user to `docker` group: `sudo usermod -aG docker $USER`, log out, log back in. |
| `seige start` hangs on `docker build` (first time) | Base images are being pulled. Cold-pull of `ubuntu:22.04` + a `pip install` takes 1-3 min per challenge depending on the image. Subsequent starts are seconds. |
| `seige connect` SSH refuses host key | The printed SSH command includes `-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null`. Use it verbatim. |
| `seige answer` returns `error: container not running` | Either run `seige start <slug>` first, or the container exited (check `docker logs seige-<slug>`). |
| State file got corrupted | `rm ~/.seige/state.json` — the player loses local scoring history but every challenge can be re-run. |

## REDACTED notes

* Every container binds **127.0.0.1 only** (`-p 127.0.0.1:0:2222`).
  No port is exposed on a routable interface. Safe to run on a
  shared network without leaking the validator.
* Challenge images are deliberately vulnerable / contain rogue
  fixtures (rogue admin entries, fake C2 IPs, sample webshells in
  /var/www). They are **training fixtures** — never deploy them
  next to real production infrastructure or expose them on a
  public IP. The bundle's images carry only the `siege/<slug>`
  namespace to make accidental pull-to-prod obvious.
* The `answer` CLI inside each container hits a loopback validator
  at 127.0.0.1:5000 *inside* the container's network namespace —
  the validator is never reachable from the host or from any other
  container.

## Sizing

Approximate sizes (single-image layer-deduped via `docker save`):

| Bundle contents | Compressed (.tar.zst) | Raw images |
|---|---|---|
| Network device live-CLI track (10 vendors) | ~280 MB | ~1.1 GB |
| Windows / AD track (5 hosts) | ~150 MB | ~600 MB |
| Linux track (1 host) | ~30 MB | ~110 MB |
| **Full bundle (everything runnable)** | **~1.6 GB** | **~6 GB** |

To trim, edit `scripts/build-offline-bundle.sh` and pass a
custom slug allowlist before the `docker save` step — easy
follow-up if you only want one track on the stick.
