# Phase 9 egress proxy: HTTP/CONNECT proxy with FQDN allowlist.
#
# Used by the `egress-proxied` container profile. The challenge container
# is attached to a per-instance internal bridge that's also connected to
# this proxy; outbound traffic must transit the proxy and pass the
# allowlist. There is no other route to the outside world from a
# `egress-proxied` instance.
#
# Pinned to a minimal alpine + tinyproxy installed from the package mirror.
# An operator pinning by digest can swap the FROM line for
# `alpine@sha256:<digest>` once they verify the upstream image.
FROM alpine:3.19

RUN apk add --no-cache tinyproxy=1.11.2-r0 ca-certificates \
    && (id tinyproxy >/dev/null 2>&1 || adduser -D -u 1001 tinyproxy) \
    && mkdir -p /var/log/tinyproxy /var/run/tinyproxy /srv/egress \
    && chown -R tinyproxy:tinyproxy /var/log/tinyproxy /var/run/tinyproxy /srv/egress

COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
COPY egress-allowlist.conf /etc/tinyproxy/egress-allowlist.conf
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER tinyproxy

EXPOSE 8888

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
