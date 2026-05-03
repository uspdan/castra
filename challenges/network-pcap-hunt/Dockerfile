FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir scapy

COPY generate_pcap.py .

RUN mkdir -p /output && python generate_pcap.py

FROM nginx:alpine

COPY --from=builder /output/capture.pcap /usr/share/nginx/html/
COPY index.html /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
