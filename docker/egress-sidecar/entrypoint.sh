#!/bin/sh
# Per-instance sidecar entrypoint.
#
# Reads the rendered tinyproxy allowlist from the EGRESS_ALLOWLIST env
# var and writes it to /etc/tinyproxy/egress-allowlist.conf before
# starting tinyproxy. Empty / unset env -> empty filter file ->
# FilterDefaultDeny Yes denies everything (safe default).
set -eu

FILTER="/etc/tinyproxy/egress-allowlist.conf"
printf '%s\n' "${EGRESS_ALLOWLIST:-}" > "$FILTER"

exec tinyproxy -d -c /etc/tinyproxy/tinyproxy.conf
