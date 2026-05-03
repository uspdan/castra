#!/bin/sh
# Egress-proxy entrypoint.
#
# The hot-reload pipeline shares a docker volume between the api and
# the egress-proxy, mounted here at /srv/egress. The api process
# writes the rendered tinyproxy allowlist to
# /srv/egress/egress-allowlist.conf; this entrypoint ensures that
# file exists before tinyproxy starts so the daemon does not crash
# when no instances have rendered yet (FilterDefaultDeny=Yes plus an
# empty filter = deny all, which is the safe default).
set -eu

FILTER="/srv/egress/egress-allowlist.conf"

if [ ! -f "$FILTER" ]; then
    # Volume is freshly initialised. Drop an empty file in place so
    # tinyproxy does not error out at startup. The api process will
    # rewrite this atomically on the next allowlist refresh.
    : > "$FILTER" 2>/dev/null || true
fi

exec tinyproxy -d -c /etc/tinyproxy/tinyproxy.conf
