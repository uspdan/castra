#!/bin/sh
set -eu
mkdir -p /run/sshd
python3 /opt/validator.py >/var/log/validator.log 2>&1 &
exec /usr/sbin/sshd -D -e
