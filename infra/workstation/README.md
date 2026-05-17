# Siege Analyst Workstation

A container that sits **inside the seige-range network** with full
reachability to every challenge host. Players connect to *this*
box from wherever they happen to be — over an exposed SSH port,
or in a browser via the platform's web-shell — and run `seige
list` / `ssh dc01` / `ssh fortigate` etc. from here.

The point: **remove the "I need VPN to my corp jumpbox" dependency**.
The workstation *is* the jumpbox. As long as the player can reach
the seige-range public endpoint (SSH on :2222 or HTTPS on :443),
they have a full analyst kit.

## What's on board

* `bash` + `zsh` + `tmux` + `vim-tiny` + `less` + `ncurses-term`
* `openssh-client` + `sshpass`
* `curl` + `wget` + `netcat-openbsd` + `dnsutils`
* `nmap` + `tcpdump` + `tshark` + `mtr-tiny`
* `jq` + `ripgrep` + `silversearcher-ag` + `xxd` + `file`
* `python3` + `pip` + `venv`
* `powershell` 7 (so the Windows challenges' cmdlets dry-run locally)
* `ttyd` — single-binary browser web-shell
* The `seige` CLI (the same one used for offline play)
* Pre-shipped `~/.ssh/config` with short aliases for every live
  challenge — `ssh dc01`, `ssh fortigate`, `ssh exch-01`, etc.
* `sudo` NOPASSWD on a tight allowlist: tcpdump / tshark / nmap.

## Deploy

```sh
# Set the analyst's password (rotate per engagement).
echo "SIEGE_WORKSTATION_PASSWORD=$(openssl rand -base64 24)" >> .env

# Bring up the workstation alongside the rest of the stack.
docker compose -f docker-compose.yml \
               -f infra/workstation/docker-compose.workstation.yml \
               up -d workstation
```

The workstation joins the existing `siege-range` user-defined
network (declared `external: true` in the override), so it can
DNS-resolve every challenge container by name as soon as the
orchestrator launches them.

## Connect

### SSH (no VPN, no browser)

```sh
ssh -p 2222 analyst@<seige-range-public-host>
# password: the one you set in .env
```

### Web shell (browser only — what you use on a phone / kiosk / no-SSH-client laptop)

The platform's nginx is configured to reverse-proxy
`https://<seige-range-host>/workstation/` to ttyd on :7681 behind
the same auth as the rest of the UI. Once authenticated as a
player you land at the analyst bash prompt — same shell, same
tools, no SSH client required.

## Use

```sh
analyst@workstation:~$ seige list
team  diff   pts  slug                                   status
------------------------------------------------------------------------------
blue  d3      500  device-cisco-ios-live                  not-started
blue  d4      600  windows-dc-live                        not-started
...

analyst@workstation:~$ seige start windows-dc-live
[seige] starting container seige-windows-dc-live...

analyst@workstation:~$ ssh dc01
hunter@seige-windows-dc-live's password: hunter
PS C:\Users\Administrator> Get-ADGroupMember "REDACTED"
...

analyst@workstation:~$ seige answer windows-dc-live 1 "REDACTED"
{"question": "1", "correct": true}

analyst@workstation:~$ seige reveal windows-dc-live
{"flag": "CTF{REDACTED}"}
```

## When to use which

| Scenario | Use |
|---|---|
| At the office, full VPN, normal flow | The platform's web UI (`/challenges`). |
| At a customer site, no corp VPN, public internet | This workstation, via SSH or `/workstation/`. |
| On a plane, no internet at all | The offline bundle (`scripts/build-offline-bundle.sh` → laptop Docker). See `docs/runbooks/offline-workstation.md`. |
| Locked-down customer laptop, no Docker, no SSH client | This workstation, browser only. |

## REDACTED posture

* SSH is **password auth on a non-root user**. Rotate the password
  per engagement via `.env`. The password is also the ttyd basic-auth
  credential.
* `sudo` is **NOPASSWD allowlisted** to `tcpdump`, `tshark`, and
  `nmap` only. No general root escalation.
* The workstation is on the **internal `siege-range` network**.
  Its only externally-published port is `2222` (SSH); `7681`
  (ttyd) is bound to loopback for nginx to proxy. Nothing else
  leaves the box without explicit egress.
* No persistent home volume by default — every container restart
  starts the analyst in a clean `/home/analyst`. Add a volume
  mount in `docker-compose.workstation.yml` if you want per-player
  state to survive restarts.
* The pre-shipped `~/.ssh/config` uses
  `StrictHostKeyChecking=no` + `UserKnownHostsFile=/dev/null`.
  Acceptable for ephemeral challenge containers where the host
  key changes every launch; do **not** copy this config to a
  laptop that connects to real production hosts.

## Tuning

The toolchain is opinionated but not load-bearing. If a particular
engagement needs different tools, edit the `Dockerfile` and rebuild:

```sh
docker compose -f docker-compose.yml \
               -f infra/workstation/docker-compose.workstation.yml \
               build workstation \
               --no-cache
```

Common adds:

* `volatility3` — `pip install volatility3` post-build. Heavy.
* `evtx_dump` / `python-evtx` — Windows event-log parser for offline
  .evtx samples players may want to compare against the live data.
* `chainsaw` / `hayabusa` — Sigma-on-evtx hunting.
* `bloodhound-python` (collector only) for AD enumeration practice
  against the DC challenge.

Keep adds **minimal and per-engagement**. The base image already
covers 90% of what a live forensics session needs.
