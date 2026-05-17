#!/bin/bash
# Siege analyst workstation entrypoint.
#
# Sets the analyst password from env, starts sshd + ttyd, waits.

set -eu

PASSWORD="${SIEGE_WORKSTATION_PASSWORD:-}"
if [[ -z "$PASSWORD" ]]; then
    echo "[workstation] SIEGE_WORKSTATION_PASSWORD not set; generating one." >&2
    PASSWORD="$(tr -dc 'A-Za-z0-9-' </dev/urandom | head -c 16)"
    echo "[workstation] analyst password: $PASSWORD"
fi
echo "analyst:${PASSWORD}" | chpasswd

# Seed /home/analyst from the skeleton on first run — when a
# persistent named volume is mounted, the directory starts empty
# on the very first container start. Copy only if nothing
# meaningful is there yet so an analyst's saved notes / history /
# scripts survive container restarts untouched.
if [[ ! -e /home/analyst/.ssh/config && -d /opt/analyst-skel ]]; then
    cp -a /opt/analyst-skel/. /home/analyst/
    chown -R analyst:analyst /home/analyst
fi

# Hostname inside the seige-range network. Player sees this as
# their prompt context.
HOSTNAME_SET="${SIEGE_WORKSTATION_HOSTNAME:-workstation}"
hostname "${HOSTNAME_SET}" || true

# sshd needs /run/sshd present (read-only rootfs strips it).
mkdir -p /run/sshd
/usr/sbin/sshd -e

# ttyd — browser shell at :7681. We bind 0.0.0.0 so nginx can
# reverse-proxy it; the orchestrator publishes the port behind
# the platform's auth. ``--uid``/``--gid`` ensure every shell
# session ttyd spawns runs as the unprivileged ``analyst`` user,
# even though this entrypoint is running as root.
ANALYST_UID="$(id -u analyst)"
ANALYST_GID="$(id -g analyst)"
exec /usr/local/bin/ttyd \
    --port 7681 \
    --interface 0.0.0.0 \
    --credential "analyst:${PASSWORD}" \
    --uid "${ANALYST_UID}" \
    --gid "${ANALYST_GID}" \
    --writable \
    bash -l
