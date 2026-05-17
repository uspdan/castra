# Player Handbook

> How to play the seige-range. Three connectivity modes, three
> levels of self-sufficiency. Pick whichever fits your situation.

## 0. Where am I?

| You are… | What works | Use |
|---|---|---|
| At the office, on corp VPN | Everything | Web UI (`/challenges`) |
| At a customer site, public internet only | Almost everything | Web UI + the **analyst workstation** (`/workstation`) |
| On a plane / in an air-gapped lab | Local challenges only | **Offline runner** (`scripts/seige`) on your laptop |
| Locked-down laptop, no Docker, no SSH client | Browser-only | **Analyst workstation web shell** at `/workstation/` |

The rest of this guide walks each mode.

---

## 1. Mode A — Browser, on VPN, normal flow

1. Open `https://<your-seige-range>/`.
2. Log in.
3. Go to **Challenges**. Filter by team / status / category /
   difficulty / search. Sort by points / difficulty / solves /
   newest.
4. Click a challenge card. The detail pane on the right shows
   the description, hints (locked / unlock costs points), and a
   big **Launch Challenge** button.
5. Click Launch. The orchestrator builds and runs a container.
   You get a host port (e.g. `10042`) and an SSH command.
6. SSH in (`ssh -p 10042 hunter@<seige-range-host>`, password
   `hunter`). Read `~/investigation.md`.
7. Investigate. Submit answers either inside the container
   (`answer 1 "value"` / `answer reveal`) or from the right-side
   panel via the **Submit Flag** form.
8. Flag accepted → points credited → leaderboard updates in
   real time over the WebSocket.

---

## 2. Mode B — Analyst workstation (no VPN to corp toolkit)

Use this when you can reach the seige-range public endpoint but
**not** your normal corp jumpbox / DFIR VM.

### Launch from the UI

1. Hit **Workstation** in the top nav (between Rankings and
   Deploy).
2. Click **Launch Workstation**. The platform spins up a
   per-user container `seige-workstation-<your-id>` on the
   seige-range network and mounts your personal
   `seige-workstation-home-<your-id>` volume at `/home/analyst`.
3. The page reveals:
   * Your **SSH command** — `ssh -p <port> analyst@<host>`.
   * The **ttyd web URL** — opens a browser shell in a new tab.
   * A **one-shot password** in a yellow panel. **Copy it now.**
     Refresh the page and you lose it forever (the only recovery
     is Stop + Launch, which preserves your `/home` but rotates
     the password).

### What you get

Inside the workstation (from `cat /etc/motd`):

```
Quick reference:

  seige list                  # every challenge + your status
  seige info <slug>           # one challenge's metadata
  ssh <alias>                 # open the challenge — `ssh dc01`,
                              #   `ssh fortigate`, `ssh exch-01`...
                              #   password: hunter
  seige answer <slug> N "x"   # submit one answer
  seige reveal <slug>         # fetch the flag once all correct
  seige score                 # how you're doing
```

Tools pre-installed:
* shell + ergonomics — bash, zsh, tmux, vim-tiny, less,
  ncurses-term
* network — openssh-client + sshpass, curl, wget, netcat-openbsd,
  dnsutils, iputils-ping, mtr-tiny, tcpdump, tshark, nmap
* data wrangling — jq, xxd, file, ripgrep, ag (silversearcher-ag)
* dev — python3 + pip + venv, git
* PowerShell 7 — dry-run the Windows-track cmdlets locally
  before pasting them into the live device shell
* `sudo` NOPASSWD for `tcpdump` / `tshark` / `nmap` only

### What persists across restarts

Mounted on a per-player named volume keyed on your user id:
* `/home/analyst/.bash_history`
* `/home/analyst/.seige/state.json` (your local solve tracker)
* Any notes, scripts, captures you save under `~`

What doesn't:
* The SSH password (fresh on every Launch)
* Running processes / loopback connections (clean state per launch)

### Stop when you're done

Click **Stop Workstation** on `/workstation`. The container
shuts down; your volume waits for you. Next Launch picks up where
you left off.

---

## 3. Mode C — Offline runner (no internet at all)

For the "I'm on a plane / in a SCIF / at a customer with a
locked-down laptop and Docker" case.

### One-time bundle build (online, on your laptop or a build host)

```sh
# Pre-build every challenge image (~10-15 min cold; cached after).
./scripts/seige pull

# Create a portable tarball.
./scripts/build-offline-bundle.sh
# -> dist/seige-offline-<YYYYMMDD>.tar.zst    (~1.6 GB)
```

The bundle contains every challenge image (deduped via
`docker save`), the `seige` CLI, and the offline runbook.

### On the air-gapped target

```sh
tar --use-compress-program=unzstd -xvf seige-offline-<DATE>.tar.zst
cd seige-offline-<DATE>
./load-images.sh            # docker load each image
./scripts/seige list        # all challenges + your status
./scripts/seige start windows-dc-live
# -> [seige] up — ssh -p 54392 hunter@127.0.0.1   (password: hunter)
./scripts/seige connect --exec windows-dc-live
# drops you straight into hunter's bash via docker exec
```

### Submit answers from outside the container

```sh
./scripts/seige answer windows-dc-live 1 "REDACTED"
./scripts/seige answer windows-dc-live 2 "REDACTED"
# ... or `answer remember` inside the SSH session, then `answer reveal`.

./scripts/seige reveal windows-dc-live
# -> {"flag":"CTF{REDACTED}"}

./scripts/seige score
# solved: 1    total points: 600
```

State lives in `~/.seige/state.json`. Survives reboots.

### Bring solves back online

When VPN access returns:

```sh
./scripts/seige sync --upstream https://your-seige-range.example
# upstream username: <your platform user>
# upstream password: ********
# [sync] authenticated as ...
# [sync] 3 solve(s) to push.
#   + windows-dc-live: ok
#   + linux-syslog-live: ok
#   + device-fortigate-live: already credited upstream (409)
# [sync] pushed 2, skipped 1, failed 0.
```

`seige sync` is **idempotent per slug**. Re-running is safe; only
unsynced rows are pushed. Already-credited solves come back 409
and we treat that as success.

---

## Deployment — operator perspective

### Bringing up the workstation feature

Once per deploy:

```sh
# Generate a default password used by the compose-overlay case
# (the platform-UI-launched per-player containers get fresh
# passwords every time).
echo "SIEGE_WORKSTATION_PASSWORD=$(openssl rand -base64 24)" >> .env

# Build the workstation image.
make workstation-build

# (Optional, for standalone testing) bring up a single shared
# workstation alongside the rest of the stack:
make workstation-up
```

The `POST /api/v1/workstation/launch` endpoint (used by the UI)
ignores the env-side password and generates a fresh one per
launch. The env-side password only applies to the optional
shared compose-overlay workstation that `make workstation-up`
brings up.

### nginx routing (optional)

To expose the per-player ttyd web shell at
`https://<host>/workstation/<user-id>/`, add a reverse-proxy
block to your nginx config. (A minimal template lives at
`infra/workstation/README.md` under "Connect → Web shell".)
Without this the player connects via SSH using the port the
launch response carries, which works but is less browser-friendly.

### Bundle distribution

For air-gapped engagements:

```sh
make offline-bundle
# -> dist/seige-offline-<YYYYMMDD>.tar.zst

# Move the bundle to the target via approved channel.
# On the target:
tar --use-compress-program=unzstd -xvf seige-offline-*.tar.zst
cd seige-offline-*
./load-images.sh
```

Bundle size grows with the catalogue. Trim by editing the slug
allowlist in `scripts/build-offline-bundle.sh` if you only want
one track on the stick.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `seige start` hangs forever | First-time pull of `ubuntu:22.04` + `pip install` takes 1-3 min per challenge. Subsequent starts are seconds. |
| `seige connect` SSH refuses host key | The printed SSH command includes `-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null`. Use it verbatim. |
| `seige answer` returns `container not running` | Either `seige start <slug>` first, or check `docker logs seige-<slug>` for crash details. |
| Workstation UI button → 503 "workstation unavailable" | Operator hasn't run `make workstation-build`. Build the image first. |
| Workstation web URL 404 | nginx route for `/workstation/<id>/` not configured. SSH path still works. |
| `~/.seige/state.json` got corrupted | `rm ~/.seige/state.json` — local scoring history goes; every challenge can be re-run. |
| `seige sync` says `login failed (429)` | Platform rate-limited the login attempt. Wait 60s and retry. |
| `seige sync` says `login failed (401)` | Wrong username/password. The CLI doesn't store credentials anywhere; you must re-enter. |

## Reference

* [`infra/workstation/README.md`](../infra/workstation/README.md) — workstation image deep-dive + tuning
* [`docs/runbooks/offline-workstation.md`](runbooks/offline-workstation.md) — offline bundle deep-dive
* [`scripts/seige`](../scripts/seige) — the CLI itself (`seige --help`)
