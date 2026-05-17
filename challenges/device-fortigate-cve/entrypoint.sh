#!/bin/sh
# Threat-hunt challenge entrypoint (factory-generated, do not hand-edit).
#
# Recreates /run/sshd (lost under read-only-rootfs + /run tmpfs),
# starts the loopback validator daemon, execs sshd in the
# foreground.

set -eu

mkdir -p /run/sshd
python3 /opt/validator.py >/var/log/validator.log 2>&1 &
exec /usr/sbin/sshd -D -e
