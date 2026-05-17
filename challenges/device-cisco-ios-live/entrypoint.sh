#!/bin/sh
# device-cisco-ios-live entrypoint.
#
# - Recreates /run/sshd (lost under read-only-rootfs + /run tmpfs).
# - Starts the validator daemon on loopback :5000.
# - Execs sshd in the foreground on the player port.

set -eu

mkdir -p /run/sshd
python3 /opt/validator.py >/var/log/validator.log 2>&1 &
exec /usr/sbin/sshd -D -e
