# Siege Analyst Workstation
#
# A container that sits inside the seige-range network with full
# reachability to every challenge host. The player connects to
# *this* box from anywhere — over an exposed SSH port, or through
# the browser via ttyd — and runs `connect <slug>` from here to
# enter each challenge. The point is to remove any "I need VPN to
# my corp jumpbox" dependency: the workstation IS the jumpbox.
#
# Image: siege/workstation:latest
#
# CLAUDE.md §12.1 notes:
# * **Digest-pinned base** (below).
# * **Single-stage** — intentional. There are no compile steps;
#   every binary lands via apt + the ttyd download. Multi-stage
#   would add complexity for zero size win.
# * **Runtime user** — the entrypoint runs as root for one
#   reason: ``chpasswd`` (set the per-launch analyst password) and
#   ``sshd`` (listen on :2222 for SSH). ttyd is then exec'd with
#   ``--uid analyst`` so every player-facing shell session runs as
#   the unprivileged ``analyst`` user; root is never exposed to
#   the player. sudo NOPASSWD is allowlisted to tcpdump / tshark
#   / nmap only — intentional trade-off documented in
#   ``docs/adr/002-workstation-security.md``.

# ubuntu:22.04 — digest pinned 2026-05-17. Refresh via
# ``docker buildx imagetools inspect ubuntu:22.04`` and the
# matching tag entry in the workstation README.
FROM ubuntu:22.04@sha256:4f838adc7181d9039ac795a7d0aba05a9bd9ecd480d294483169c5def983b64d

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# ----------------------------------------------------------------------
# Base toolchain — opinionated DFIR/network analyst kit. Keep it
# focused: one good tool per job, not five.
# ----------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        # shell + ergonomics
        bash zsh tmux screen less vim-tiny ncurses-term \
        # network analyst basics
        openssh-server openssh-client sshpass \
        curl wget netcat-openbsd dnsutils \
        iputils-ping iputils-tracepath mtr-tiny tcpdump tshark nmap \
        # file / data wrangling
        jq xxd file ripgrep silversearcher-ag \
        # python + the bits the seige CLI uses
        python3 python3-pip python3-venv \
        # source control + diff
        git \
        # service mgmt
        sudo ca-certificates gnupg passwd \
    && rm -rf /var/lib/apt/lists/*

# PowerShell 7 (so the player can dry-run the Windows challenge
# cmdlets locally before pasting them into the live device shell).
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/ubuntu/22.04/prod jammy main" \
        > /etc/apt/sources.list.d/microsoft.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends powershell \
    && rm -rf /var/lib/apt/lists/*

# ttyd — single-binary web terminal. Serves an xterm.js shell over
# WebSocket so the player can land in bash from a browser tab
# instead of needing an SSH client.
ARG TTYD_VERSION=1.7.7
RUN curl -fsSL "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.x86_64" \
        -o /usr/local/bin/ttyd \
    && chmod +x /usr/local/bin/ttyd

# SSH server config — non-root, password auth (the player picks
# their own password at deploy via SIEGE_WORKSTATION_PASSWORD).
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config \
    && sed -i 's/#Port 22/Port 2222/' /etc/ssh/sshd_config

# Player account.
RUN useradd -m -s /bin/bash analyst \
    && echo 'analyst ALL=(ALL) NOPASSWD: /usr/bin/tcpdump, /usr/bin/tshark, /usr/bin/nmap' \
        > /etc/sudoers.d/analyst-tools

# Ship the seige CLI and an SSH config that aliases every known
# challenge slug to the docker DNS name the orchestrator gives it.
# The orchestrator joins each challenge container to the
# `siege-range` user-defined network, so DNS within that network
# resolves <container-name>.
COPY scripts/seige /usr/local/bin/seige
COPY infra/workstation/motd /etc/motd
COPY infra/workstation/entrypoint.sh /usr/local/bin/entrypoint.sh

# Skeleton for /home/analyst — copied into the live home on first
# run *only if* the home directory is empty. This lets a
# persistent named volume mount at /home/analyst without masking
# the baked-in ssh-config / shell rc files.
COPY infra/workstation/ssh-config /opt/analyst-skel/.ssh/config
RUN printf '%s\n%s\n' 'export PS1="\u@\h:\w$ "' 'cat /etc/motd' \
        > /opt/analyst-skel/.bashrc \
    && chmod 0644 /opt/analyst-skel/.ssh/config /opt/analyst-skel/.bashrc \
    && chmod 0700 /opt/analyst-skel/.ssh \
    && chown -R analyst:analyst /opt/analyst-skel \
    && chmod 0755 /usr/local/bin/seige /usr/local/bin/entrypoint.sh

# Two ports:
#   2222 — SSH
#   7681 — ttyd browser shell (nginx fronts this at /workstation/)
EXPOSE 2222 7681

CMD ["/usr/local/bin/entrypoint.sh"]
