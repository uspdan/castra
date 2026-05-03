"""Generate 10000 syslog-format lines including a brute force attack pattern."""

import random
import os
from datetime import datetime, timedelta

random.seed(42)

normal_ips = [
    "10.0.0.10", "10.0.0.11", "10.0.0.12", "10.0.0.15", "10.0.0.20",
    "10.0.0.25", "10.0.0.30", "10.0.0.35", "10.0.0.40", "10.0.0.50",
    "192.168.1.100", "192.168.1.105", "192.168.1.110",
]

normal_users = ["jsmith", "apark", "mwilson", "ljones", "kbrown", "dlee", "rgarcia", "tchen"]

web_paths = [
    "/index.html", "/about", "/api/users", "/api/status", "/dashboard",
    "/login", "/logout", "/settings", "/profile", "/reports",
    "/api/data", "/health", "/metrics", "/static/style.css", "/static/app.js",
]

http_codes = [200, 200, 200, 200, 200, 301, 304, 404, 403, 500]

services = ["sshd", "nginx", "systemd", "cron", "kernel", "sudo"]

logs = []

# Base start time
base_time = datetime(2024, 3, 15, 0, 0, 0)

# Generate normal logs spread across the day (about 9500)
for i in range(9500):
    offset = timedelta(seconds=random.randint(0, 86400))
    ts = base_time + offset
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    log_type = random.choice(["ssh_ok", "ssh_ok", "web", "web", "web", "system", "system"])

    if log_type == "ssh_ok":
        ip = random.choice(normal_ips)
        user = random.choice(normal_users)
        action = random.choice(["Accepted password", "Accepted publickey", "session opened", "session closed"])
        if action.startswith("session"):
            line = f"{ts_str} server1 sshd[{random.randint(1000,9999)}]: pam_unix(sshd:session): {action} for user {user}"
        else:
            line = f"{ts_str} server1 sshd[{random.randint(1000,9999)}]: {action} for {user} from {ip} port {random.randint(40000,65000)} ssh2"
    elif log_type == "web":
        ip = random.choice(normal_ips)
        path = random.choice(web_paths)
        code = random.choice(http_codes)
        size = random.randint(200, 50000)
        line = f"{ts_str} server1 nginx: {ip} - - \"{random.choice(['GET','POST'])} {path} HTTP/1.1\" {code} {size}"
    else:
        service = random.choice(services)
        messages = [
            "Started Session",
            "Finished cleanup",
            "Reloading configuration",
            "Service started successfully",
            "Rotating logs",
            "Memory usage normal",
            "Disk check passed",
            "NTP sync completed",
        ]
        line = f"{ts_str} server1 {service}[{random.randint(100,9999)}]: {random.choice(messages)}"

    logs.append((ts, line))

# Generate brute force attack: 500 failed logins from 10.0.0.47 within 10 minutes
# Starting at 14:13:47 so the success is at 14:23:47
attack_start = datetime(2024, 3, 15, 14, 13, 47)
for i in range(500):
    offset = timedelta(seconds=random.randint(0, 600))  # within 10 minutes
    ts = attack_start + offset
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    pid = random.randint(10000, 19999)
    line = f"{ts_str} server1 sshd[{pid}]: Failed password for admin from 10.0.0.47 port {random.randint(40000,65000)} ssh2"
    logs.append((ts, line))

# Successful login after brute force
success_ts = datetime(2024, 3, 15, 14, 23, 47)
success_line = f"2024-03-15T14:23:47Z server1 sshd[20001]: Accepted password for admin from 10.0.0.47 port 54321 ssh2"
logs.append((success_ts, success_line))

# Sort by timestamp
logs.sort(key=lambda x: x[0])

os.makedirs("/data", exist_ok=True)
with open("/data/logs.txt", "w") as f:
    for _, line in logs:
        f.write(line + "\n")

print(f"Generated {len(logs)} log entries to /data/logs.txt")
