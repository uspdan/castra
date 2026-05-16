#!/bin/sh
# Threat-hunt challenge entrypoint.
#
# Recreates /run/sshd (lost when /run is mounted as tmpfs under the
# read-only-rootfs sandbox profile), launches the loopback validator
# daemon, then execs sshd in the foreground.

set -eu

mkdir -p /run/sshd

# Validator backend — answers + scoring server. Listens on 127.0.0.1
# only so the player can't bypass the answer CLI by hitting the
# socket directly from outside the container.
python3 /opt/validator.py >/var/log/validator.log 2>&1 &

exec /usr/sbin/sshd -D -e
