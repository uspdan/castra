FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir scapy

COPY generate_pcap.py .

RUN mkdir -p /output && python generate_pcap.py

FROM nginx:alpine

COPY --from=builder /output/capture.pcap /usr/share/nginx/html/
COPY index.html /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

# /var/log is mounted as a fresh tmpfs at launch under the
# read-only-rootfs sandbox profile; the image-baked /var/log/nginx
# subdir is lost. Recreate it before nginx starts and redirect to
# stdout/stderr for log collection.
RUN echo '#!/bin/sh' > /docker-entrypoint.d/99-recreate-log-dir.sh && \
    echo 'mkdir -p /var/log/nginx && ln -sf /dev/stdout /var/log/nginx/access.log && ln -sf /dev/stderr /var/log/nginx/error.log' >> /docker-entrypoint.d/99-recreate-log-dir.sh && \
    chmod +x /docker-entrypoint.d/99-recreate-log-dir.sh

EXPOSE 8080
