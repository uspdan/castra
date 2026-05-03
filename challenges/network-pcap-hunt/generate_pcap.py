#!/usr/bin/env python3
"""Generate a PCAP file with mixed traffic containing a hidden flag in an HTTP POST."""

import random
import struct
import os

# We'll build raw PCAP manually to avoid scapy import issues in minimal environments
# PCAP file format: global header + packet records

PCAP_MAGIC = 0xa1b2c3d4
PCAP_VERSION_MAJOR = 2
PCAP_VERSION_MINOR = 4
PCAP_THISZONE = 0
PCAP_SIGFIGS = 0
PCAP_SNAPLEN = 65535
PCAP_NETWORK = 1  # LINKTYPE_ETHERNET

OUTPUT_PATH = '/output/capture.pcap'

FLAG = 'CTF{REDACTED}'


def write_pcap_header(f):
    f.write(struct.pack('<IHHiIII',
        PCAP_MAGIC, PCAP_VERSION_MAJOR, PCAP_VERSION_MINOR,
        PCAP_THISZONE, PCAP_SIGFIGS, PCAP_SNAPLEN, PCAP_NETWORK))


def write_packet(f, timestamp_sec, data):
    ts_sec = timestamp_sec
    ts_usec = random.randint(0, 999999)
    incl_len = len(data)
    orig_len = len(data)
    f.write(struct.pack('<IIII', ts_sec, ts_usec, incl_len, orig_len))
    f.write(data)


def mac_bytes(mac_str='00:11:22:33:44:55'):
    return bytes(int(b, 16) for b in mac_str.split(':'))


def build_ethernet(src_mac, dst_mac, ethertype, payload):
    return dst_mac + src_mac + struct.pack('!H', ethertype) + payload


def ip_checksum(header):
    if len(header) % 2 != 0:
        header += b'\x00'
    s = 0
    for i in range(0, len(header), 2):
        w = (header[i] << 8) + header[i + 1]
        s += w
    while s >> 16:
        s = (s & 0xFFFF) + (s >> 16)
    return ~s & 0xFFFF


def build_ip(src_ip, dst_ip, protocol, payload):
    version_ihl = 0x45
    dscp_ecn = 0
    total_length = 20 + len(payload)
    identification = random.randint(0, 65535)
    flags_fragment = 0x4000  # Don't fragment
    ttl = 64
    checksum = 0

    src = bytes(int(b) for b in src_ip.split('.'))
    dst = bytes(int(b) for b in dst_ip.split('.'))

    header = struct.pack('!BBHHHBBH4s4s',
        version_ihl, dscp_ecn, total_length, identification,
        flags_fragment, ttl, protocol, checksum, src, dst)

    checksum = ip_checksum(header)
    header = struct.pack('!BBHHHBBH4s4s',
        version_ihl, dscp_ecn, total_length, identification,
        flags_fragment, ttl, protocol, checksum, src, dst)

    return header + payload


def build_tcp(src_port, dst_port, seq, ack, flags, payload):
    data_offset = 5 << 4
    window = 65535
    checksum = 0  # Simplified - not computing TCP checksum
    urgent = 0

    header = struct.pack('!HHIIBBHHH',
        src_port, dst_port, seq, ack, data_offset, flags,
        window, checksum, urgent)

    return header + payload


def build_udp(src_port, dst_port, payload):
    length = 8 + len(payload)
    checksum = 0
    header = struct.pack('!HHHH', src_port, dst_port, length, checksum)
    return header + payload


def build_dns_query(domain):
    """Build a simple DNS query packet."""
    tx_id = random.randint(0, 65535)
    flags = 0x0100  # Standard query
    questions = 1
    header = struct.pack('!HHHHHH', tx_id, flags, questions, 0, 0, 0)

    # Encode domain name
    qname = b''
    for label in domain.split('.'):
        qname += bytes([len(label)]) + label.encode()
    qname += b'\x00'

    # QTYPE=A, QCLASS=IN
    question = qname + struct.pack('!HH', 1, 1)

    return header + question


def build_http_request(method, path, host, body=None):
    """Build an HTTP request as bytes."""
    lines = [f'{method} {path} HTTP/1.1', f'Host: {host}', 'User-Agent: Mozilla/5.0', 'Accept: */*']
    if body:
        lines.append(f'Content-Length: {len(body)}')
        lines.append('Content-Type: application/x-www-form-urlencoded')
    lines.append('Connection: close')
    lines.append('')
    if body:
        lines.append(body)
    else:
        lines.append('')
    return '\r\n'.join(lines).encode()


def build_http_response(status, body):
    """Build an HTTP response as bytes."""
    lines = [
        f'HTTP/1.1 {status}',
        'Server: nginx/1.24.0',
        f'Content-Length: {len(body)}',
        'Content-Type: text/html',
        'Connection: close',
        '',
        body
    ]
    return '\r\n'.join(lines).encode()


def generate():
    os.makedirs('/output', exist_ok=True)

    client_mac = mac_bytes('aa:bb:cc:dd:ee:01')
    server_mac = mac_bytes('aa:bb:cc:dd:ee:02')
    dns_mac = mac_bytes('aa:bb:cc:dd:ee:03')

    client_ip = '192.168.1.100'
    server_ip = '10.0.0.50'
    dns_ip = '8.8.8.8'

    base_time = 1700000000
    packets = []

    # Generate DNS queries
    domains = ['www.example.com', 'api.target.com', 'cdn.assets.net', 'login.portal.com',
               'images.hosting.io', 'mail.server.org', 'news.feed.com', 'docs.internal.net']

    for i, domain in enumerate(domains):
        ts = base_time + i * 2
        dns_payload = build_dns_query(domain)
        udp = build_udp(random.randint(49152, 65535), 53, dns_payload)
        ip = build_ip(client_ip, dns_ip, 17, udp)
        eth = build_ethernet(client_mac, dns_mac, 0x0800, ip)
        packets.append((ts, eth))

    # Generate normal HTTP GET requests
    paths = ['/index.html', '/about', '/contact', '/products', '/api/v1/status',
             '/images/logo.png', '/css/style.css', '/js/app.js', '/api/v1/users',
             '/dashboard', '/settings', '/profile', '/search?q=test',
             '/api/v1/health', '/robots.txt', '/sitemap.xml', '/favicon.ico',
             '/blog/post-1', '/blog/post-2', '/docs/getting-started',
             '/api/v1/config', '/static/bundle.js', '/fonts/roboto.woff2']

    seq = 1000
    for i, path in enumerate(paths):
        ts = base_time + 20 + i * 3
        src_port = random.randint(49152, 65535)

        # SYN
        tcp_syn = build_tcp(src_port, 80, seq, 0, 0x02, b'')
        ip_syn = build_ip(client_ip, server_ip, 6, tcp_syn)
        eth_syn = build_ethernet(client_mac, server_mac, 0x0800, ip_syn)
        packets.append((ts, eth_syn))

        # HTTP GET request
        http_req = build_http_request('GET', path, 'api.target.com')
        tcp_data = build_tcp(src_port, 80, seq + 1, 1, 0x18, http_req)
        ip_data = build_ip(client_ip, server_ip, 6, tcp_data)
        eth_data = build_ethernet(client_mac, server_mac, 0x0800, ip_data)
        packets.append((ts + 1, eth_data))

        # HTTP Response
        resp_body = f'<html><body>Page: {path}</body></html>'
        http_resp = build_http_response('200 OK', resp_body)
        tcp_resp = build_tcp(80, src_port, 1, seq + 1 + len(http_req), 0x18, http_resp)
        ip_resp = build_ip(server_ip, client_ip, 6, tcp_resp)
        eth_resp = build_ethernet(server_mac, client_mac, 0x0800, ip_resp)
        packets.append((ts + 2, eth_resp))

        seq += 2000

    # THE KEY PACKET: HTTP POST to /login with credentials containing the flag
    login_ts = base_time + 120
    login_port = 54321
    login_body = f'username=admin&password={FLAG}'
    http_login = build_http_request('POST', '/login', 'login.portal.com', login_body)
    tcp_login = build_tcp(login_port, 80, 50000, 1, 0x18, http_login)
    ip_login = build_ip(client_ip, server_ip, 6, tcp_login)
    eth_login = build_ethernet(client_mac, server_mac, 0x0800, ip_login)
    packets.append((login_ts, eth_login))

    # Login response
    login_resp = build_http_response('302 Found', '<html><body>Redirecting...</body></html>')
    tcp_login_resp = build_tcp(80, login_port, 1, 50000 + len(http_login), 0x18, login_resp)
    ip_login_resp = build_ip(server_ip, client_ip, 6, tcp_login_resp)
    eth_login_resp = build_ethernet(server_mac, client_mac, 0x0800, ip_login_resp)
    packets.append((login_ts + 1, eth_login_resp))

    # More noise: additional GET requests after login
    noise_paths = ['/dashboard', '/api/v1/me', '/notifications', '/settings/profile',
                   '/api/v1/data?page=1', '/api/v1/data?page=2', '/logout',
                   '/static/analytics.js', '/api/v1/metrics', '/health']

    for i, path in enumerate(noise_paths):
        ts = base_time + 150 + i * 4
        src_port = random.randint(49152, 65535)

        http_req = build_http_request('GET', path, 'api.target.com')
        tcp_data = build_tcp(src_port, 80, seq, 1, 0x18, http_req)
        ip_data = build_ip(client_ip, server_ip, 6, tcp_data)
        eth_data = build_ethernet(client_mac, server_mac, 0x0800, ip_data)
        packets.append((ts, eth_data))
        seq += 1000

    # More DNS queries for noise
    extra_domains = ['tracker.analytics.com', 'cdn.jquery.com', 'fonts.googleapis.com',
                     'api.stripe.com', 'sentry.io', 'updates.service.net']
    for i, domain in enumerate(extra_domains):
        ts = base_time + 200 + i * 5
        dns_payload = build_dns_query(domain)
        udp = build_udp(random.randint(49152, 65535), 53, dns_payload)
        ip = build_ip(client_ip, dns_ip, 17, udp)
        eth = build_ethernet(client_mac, dns_mac, 0x0800, ip)
        packets.append((ts, eth))

    # Sort packets by timestamp
    packets.sort(key=lambda x: x[0])

    # Write PCAP file
    with open(OUTPUT_PATH, 'wb') as f:
        write_pcap_header(f)
        for ts, data in packets:
            write_packet(f, ts, data)

    print(f'Generated {len(packets)} packets in {OUTPUT_PATH}')


if __name__ == '__main__':
    generate()
