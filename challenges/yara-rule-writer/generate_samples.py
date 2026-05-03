"""Generate 20 sample files: 5 malware, 15 benign."""

import os
import random
import struct

random.seed(42)

SAMPLES_DIR = "/samples"
os.makedirs(SAMPLES_DIR, exist_ok=True)

# XOR key for encoding
XOR_KEY = 0x5A

def xor_encode(data, key):
    return bytes([b ^ key for b in data])

MALWARE_BEACON = b"SIEGE_MALWARE_BEACON"
MUTEX_NAME = b"Global\\SiegeRangeC2Mutex"
USER_AGENT = b"Mozilla/5.0 SiegeAgent/1.0"

# Metadata file to track which are malware
manifest = {}

# Generate 5 malware samples
for i in range(5):
    filename = f"sample_{i+1:03d}.bin"
    filepath = os.path.join(SAMPLES_DIR, filename)

    content = bytearray()
    # PE-like header stub
    content.extend(b"MZ" + os.urandom(60))
    # Random padding
    content.extend(os.urandom(random.randint(200, 500)))
    # XOR-encoded beacon
    content.extend(xor_encode(MALWARE_BEACON, XOR_KEY))
    # More random padding
    content.extend(os.urandom(random.randint(100, 300)))
    # Mutex name in plaintext
    content.extend(MUTEX_NAME)
    # Random padding
    content.extend(os.urandom(random.randint(100, 200)))
    # User-agent string
    content.extend(USER_AGENT)
    # Trailing random data
    content.extend(os.urandom(random.randint(200, 500)))

    with open(filepath, "wb") as f:
        f.write(bytes(content))

    manifest[filename] = "malware"

# Generate 15 benign samples with some partial pattern overlap to make it tricky
benign_snippets = [
    b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    b"CreateMutex(NULL, FALSE, \"Global\\\\AppMutex\")",
    b"HTTP/1.1 200 OK\r\nContent-Type: text/html",
    b"SELECT * FROM users WHERE id = ?",
    b"BEGIN TRANSACTION; INSERT INTO logs",
    b"void main() { printf(\"Hello World\"); }",
    b"Copyright (c) 2024 Acme Corporation",
    b"Licensed under the Apache License, Version 2.0",
    b"def calculate_checksum(data):",
    b"BEACON_INTERVAL = 60",  # partial match for BEACON
    b"SiegeWare Antivirus v2.0",  # partial match for Siege
    b"Global\\SystemHealthCheck",  # partial match for Global\ mutex pattern
    b"UserAgent: Mozilla/5.0 Chrome/120",  # similar but different user agent
    b"MALWARE_SCAN_RESULT: clean",  # contains MALWARE but in different context
    b"Range: bytes=0-1024",  # partial match for Range
]

for i in range(15):
    filename = f"sample_{i+6:03d}.bin"
    filepath = os.path.join(SAMPLES_DIR, filename)

    content = bytearray()
    # Some benign files start with PE header to look like executables
    if random.random() > 0.5:
        content.extend(b"MZ" + os.urandom(60))
    else:
        content.extend(os.urandom(62))

    # Add 2-3 random benign snippets
    chosen = random.sample(benign_snippets, random.randint(2, 3))
    for snippet in chosen:
        content.extend(os.urandom(random.randint(100, 300)))
        content.extend(snippet)

    # Trailing random data
    content.extend(os.urandom(random.randint(300, 800)))

    with open(filepath, "wb") as f:
        f.write(bytes(content))

    manifest[filename] = "benign"

# Save manifest
import json
with open(os.path.join(SAMPLES_DIR, "manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

print(f"Generated {len(manifest)} samples in {SAMPLES_DIR}")
for name, label in sorted(manifest.items()):
    print(f"  {name}: {label}")
