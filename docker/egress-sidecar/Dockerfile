# Per-instance egress proxy sidecar.
#
# One sidecar per ``egress-proxied-sidecar`` challenge instance. The
# launcher passes the rendered allowlist via the ``EGRESS_ALLOWLIST``
# environment variable; the entrypoint writes it to the filter file
# before starting tinyproxy. Sidecars die with their instance — no
# hot-reload pipeline needed.
FROM alpine:3.19

RUN apk add --no-cache tinyproxy=1.11.1-r2 ca-certificates \
    && adduser -D -u 1001 tinyproxy \
    && mkdir -p /var/log/tinyproxy /var/run/tinyproxy /etc/tinyproxy \
    && chown -R tinyproxy:tinyproxy /var/log/tinyproxy /var/run/tinyproxy /etc/tinyproxy

COPY tinyproxy.conf /etc/tinyproxy/tinyproxy.conf
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

USER tinyproxy

EXPOSE 8888

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
