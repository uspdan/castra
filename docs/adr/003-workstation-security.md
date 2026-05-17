# ADR 003 — Analyst Workstation REDACTED Posture

**Status**: accepted (2026-05-17)
**Context**: `infra/workstation/` ships a per-player Ubuntu container
that lives inside the seige-range network with full reachability
to every challenge container. It exposes both SSH (port 11100+uid
on the orchestrator's compose-published range) and a browser
web shell via ttyd (port 11000+uid). This ADR records the three
non-trivial security decisions the design takes.

---

## 1. `VOLUMES=1` on the docker-socket-proxy

### Context

The platform's docker-socket-proxy (`tecnativa/docker-socket-proxy`)
originally allowed only `CONTAINERS`, `NETWORKS`, `IMAGES` (read +
`POST` for the launcher).  Workstation launches need to create a
per-user named volume (`seige-workstation-home-<uid>`) so the
analyst's home survives container restart. That requires
`VOLUMES=1`.

### Decision

`VOLUMES=1` is added to the docker-socket-proxy allowlist.

### Consequences

* The api can now `volume create/list/inspect/remove`. A
  compromised api could prune or otherwise tamper with player
  home volumes. Mitigation: per-user volume naming
  (`seige-workstation-home-<uid>`) gives the audit ledger a
  stable resource_id; volume mutations are tied to the actor
  via the existing audit chain.
* The api still cannot mount host paths, attach to the docker
  socket, run privileged containers, exec arbitrary commands —
  all of those remain in the default-deny set of the proxy.

### Alternatives rejected

* **Bind mounts** instead of named volumes — would require
  granting host-path access (`PIDS=1` + raw filesystem access
  via bind), much wider blast radius.
* **No persistence** at all — defeats the workstation's value
  proposition (analyst notes + `~/.seige/state.json` would die
  on every restart).

---

## 2. `sudo NOPASSWD` allowlist for tcpdump / tshark / nmap

### Context

A working analyst kit needs raw-socket access for pcap, ARP
inspection, and connection probing. `tcpdump` and `tshark`
require `CAP_NET_RAW`; `nmap`'s SYN-scan needs `CAP_NET_RAW` +
`CAP_NET_ADMIN`. Granting these via `cap_add` on the container
is one option; granting `sudo NOPASSWD` for those three specific
binaries is another.

### Decision

The Dockerfile ships
`/etc/sudoers.d/analyst-tools`:
```
analyst ALL=(ALL) NOPASSWD: /usr/bin/tcpdump, /usr/bin/tshark, /usr/bin/nmap
```

### Consequences

* **tcpdump-as-root is a privilege escalation primitive.**
  `tcpdump -w /etc/shadow` or `tcpdump -G ... -z /tmp/x.sh`
  (the `-z` post-rotation hook) both let an analyst escalate to
  root inside the container. We accept this trade-off because:
  1. The workstation runs **as one player**, so the only thing
     they can escalate against is their own image — and they're
     supposed to be inside that image already.
  2. The container's host-fs and network egress are still
     constrained by the existing seccomp + bind mount posture.
  3. The audit ledger captures `workstation.launch /
     workstation.stop` events so any forensic investigation can
     correlate a privilege event to a session.
* tshark + nmap have similar (smaller) primitives.
* `Defender::Allowlist sudo` won't accept this pattern in a
  shared multi-tenant range; in that case prefer the
  `cap_add` route and remove the sudo grant.

### Alternatives rejected

* **`cap_add: [NET_RAW, NET_ADMIN]`** with no sudo — cleaner in
  theory but caps apply to all processes in the container, not
  just these binaries. Setuid file caps on each binary would
  achieve the same end with more setup.
* **Run pcap on the host via a side-car**, exposing a privileged
  capture endpoint to the analyst — much more infra, doesn't
  match the "self-contained workstation" model.

---

## 3. One-shot password in the launch JSON response

### Context

Each workstation launch generates a fresh 20-char alphanumeric
password and returns it in the launch response. The frontend
displays it once with a "capture it now" panel. If the player
refreshes or navigates away, the password is gone — they have
to stop + relaunch.

### Decision

The password is **plaintext in the JSON response** and **plaintext
in memory in the frontend** until the player navigates away. It is
**never persisted** on the server (not in the DB, not in audit
payload, not in logs).

### Consequences

* Anyone with read access to the response intercepts the password
  for the lifetime of that workstation. In prod, this means: TLS
  terminator (nginx) + downstream session storage (browser localStorage
  by default with the existing auth store). Both are inside the
  platform's TLS perimeter.
* The audit ledger entry for `workstation.launch` records
  `container`, `ssh_host_port`, `web_host_port` — **not** the
  password. So even an attacker who gains DB access cannot
  retroactively use the password.
* Stop + relaunch is the recovery path. The home volume is
  preserved across the cycle.

### Alternatives rejected

* **SSH key pair issuance** — would require generating an SSH
  keypair per launch, returning the private key to the player,
  authorising the public key against analyst's
  `~/.ssh/authorized_keys`. Cleaner long-term, but adds material
  complexity for marginal benefit over a high-entropy password
  delivered over TLS.
* **Password reset endpoint** — allowing the player to "reissue"
  the password via a separate call lets them recover from a lost
  copy without losing session state. Defer to a future iteration
  if churn is high.

---

## Open follow-ups (not blocking ship)

* The workstation container has full network reachability to
  every running challenge in the player's own per-instance
  networks via the launcher's attach hook. It does **not** have
  reachability to other players' challenges. Verified by docker
  network isolation at the per-instance level.
* If a workstation is compromised by an analyst attempting to
  pivot to another player's data, the only attack surface is the
  shared seige-range docker network (via the orchestrator). The
  orchestrator's existing forbidden-list (`enforce_no_forbidden`)
  + read-only rootfs + tmpfs on challenge containers are the
  intended defence.
