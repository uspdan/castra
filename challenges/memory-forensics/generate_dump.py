"""Generate simulated memory dump data."""

import json
import base64
import os
import random

random.seed(42)

FLAG = "CTF{REDACTED}"
FLAG_B64 = base64.b64encode(FLAG.encode()).decode()

# Process list - normal Windows processes + one suspicious
process_list = [
    {"pid": 4, "ppid": 0, "name": "System", "user": "SYSTEM", "threads": 164, "handles": 2048, "start_time": "2024-03-15T08:00:00Z"},
    {"pid": 88, "ppid": 4, "name": "Registry", "user": "SYSTEM", "threads": 4, "handles": 0, "start_time": "2024-03-15T08:00:00Z"},
    {"pid": 392, "ppid": 4, "name": "smss.exe", "user": "SYSTEM", "threads": 2, "handles": 53, "start_time": "2024-03-15T08:00:01Z"},
    {"pid": 520, "ppid": 392, "name": "csrss.exe", "user": "SYSTEM", "threads": 12, "handles": 563, "start_time": "2024-03-15T08:00:02Z"},
    {"pid": 596, "ppid": 392, "name": "wininit.exe", "user": "SYSTEM", "threads": 1, "handles": 158, "start_time": "2024-03-15T08:00:02Z"},
    {"pid": 672, "ppid": 596, "name": "services.exe", "user": "SYSTEM", "threads": 8, "handles": 312, "start_time": "2024-03-15T08:00:03Z"},
    {"pid": 684, "ppid": 596, "name": "lsass.exe", "user": "SYSTEM", "threads": 10, "handles": 782, "start_time": "2024-03-15T08:00:03Z"},
    {"pid": 780, "ppid": 672, "name": "svchost.exe", "user": "SYSTEM", "threads": 22, "handles": 512, "start_time": "2024-03-15T08:00:04Z"},
    {"pid": 848, "ppid": 672, "name": "svchost.exe", "user": "NETWORK SERVICE", "threads": 15, "handles": 389, "start_time": "2024-03-15T08:00:04Z"},
    {"pid": 1024, "ppid": 672, "name": "svchost.exe", "user": "REDACTED SERVICE", "threads": 18, "handles": 445, "start_time": "2024-03-15T08:00:05Z"},
    {"pid": 1200, "ppid": 672, "name": "spoolsv.exe", "user": "SYSTEM", "threads": 7, "handles": 287, "start_time": "2024-03-15T08:00:06Z"},
    {"pid": 2104, "ppid": 2080, "name": "explorer.exe", "user": "DESKTOP\\john", "threads": 45, "handles": 1892, "start_time": "2024-03-15T08:01:30Z"},
    {"pid": 3256, "ppid": 2104, "name": "chrome.exe", "user": "DESKTOP\\john", "threads": 28, "handles": 423, "start_time": "2024-03-15T09:15:22Z"},
    {"pid": 3400, "ppid": 3256, "name": "chrome.exe", "user": "DESKTOP\\john", "threads": 12, "handles": 189, "start_time": "2024-03-15T09:15:23Z"},
    {"pid": 3788, "ppid": 2104, "name": "notepad.exe", "user": "DESKTOP\\john", "threads": 3, "handles": 78, "start_time": "2024-03-15T10:05:11Z"},
    # Suspicious process - masquerading as svchost with underscore
    {"pid": 4892, "ppid": 2104, "name": "svchost_update.exe", "user": "DESKTOP\\john", "threads": 2, "handles": 156, "start_time": "2024-03-15T13:47:22Z"},
]

# Network connections
network_connections = [
    {"pid": 780, "name": "svchost.exe", "local_addr": "0.0.0.0", "local_port": 135, "remote_addr": "*", "remote_port": "*", "state": "LISTENING", "protocol": "TCPv4"},
    {"pid": 848, "name": "svchost.exe", "local_addr": "0.0.0.0", "local_port": 445, "remote_addr": "*", "remote_port": "*", "state": "LISTENING", "protocol": "TCPv4"},
    {"pid": 3256, "name": "chrome.exe", "local_addr": "192.168.1.105", "local_port": 52341, "remote_addr": "142.250.80.46", "remote_port": 443, "state": "ESTABLISHED", "protocol": "TCPv4"},
    {"pid": 3256, "name": "chrome.exe", "local_addr": "192.168.1.105", "local_port": 52342, "remote_addr": "142.250.80.46", "remote_port": 443, "state": "ESTABLISHED", "protocol": "TCPv4"},
    {"pid": 3400, "name": "chrome.exe", "local_addr": "192.168.1.105", "local_port": 52350, "remote_addr": "151.101.1.140", "remote_port": 443, "state": "ESTABLISHED", "protocol": "TCPv4"},
    {"pid": 684, "name": "lsass.exe", "local_addr": "0.0.0.0", "local_port": 49664, "remote_addr": "*", "remote_port": "*", "state": "LISTENING", "protocol": "TCPv4"},
    {"pid": 2104, "name": "explorer.exe", "local_addr": "192.168.1.105", "local_port": 53100, "remote_addr": "204.79.197.200", "remote_port": 443, "state": "ESTABLISHED", "protocol": "TCPv4"},
    # Suspicious connection from svchost_update.exe to known bad IP
    {"pid": 4892, "name": "svchost_update.exe", "local_addr": "192.168.1.105", "local_port": 49998, "remote_addr": "185.141.27.3", "remote_port": 443, "state": "ESTABLISHED", "protocol": "TCPv4"},
    {"pid": 4892, "name": "svchost_update.exe", "local_addr": "192.168.1.105", "local_port": 50001, "remote_addr": "185.141.27.3", "remote_port": 8443, "state": "ESTABLISHED", "protocol": "TCPv4"},
]

# Strings extracted per PID
strings_data = {
    "4": ["\\SystemRoot\\System32\\ntoskrnl.exe", "Windows NT", "NTFS", "\\Registry\\Machine\\System"],
    "780": ["svchost.exe -k netsvcs", "RpcSs", "DcomLaunch", "C:\\Windows\\System32\\svchost.exe"],
    "848": ["svchost.exe -k NetworkService", "NlaSvc", "Dhcp", "C:\\Windows\\System32\\svchost.exe"],
    "1024": ["svchost.exe -k LocalService", "EventLog", "PlugPlay", "C:\\Windows\\System32\\svchost.exe"],
    "684": ["lsass.exe", "Kerberos", "NTLM", "REDACTED Accounts Manager", "C:\\Windows\\System32\\lsass.exe"],
    "2104": ["explorer.exe", "C:\\Windows\\explorer.exe", "Shell_TrayWnd", "Start Menu"],
    "3256": ["chrome.exe", "--type=browser", "Google Chrome", "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "https://www.google.com", "user-data-dir"],
    "3400": ["chrome.exe", "--type=renderer", "Google Chrome", "https://stackoverflow.com"],
    "3788": ["notepad.exe", "C:\\Windows\\System32\\notepad.exe", "Untitled - Notepad", "report_q1.txt"],
    "4892": [
        "svchost_update.exe",
        "C:\\Users\\john\\AppData\\Local\\Temp\\svchost_update.exe",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "POST /api/beacon HTTP/1.1",
        "Host: 185.141.27.3",
        "Content-Type: application/octet-stream",
        FLAG_B64,
        "REDACTED /c whoami",
        "REDACTED /c ipconfig /all",
        "REDACTED /c net user",
        "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
        "Global\\SiegeUpdateMutex",
        "kernel32.dll",
        "VirtualAlloc",
        "CreateRemoteThread",
        "NtQueryInformationProcess",
        "anti-debug check",
        "sleep 30000",
    ],
}

dump = {
    "process_list": process_list,
    "network_connections": network_connections,
    "strings": strings_data,
}

os.makedirs("/data", exist_ok=True)
with open("/data/dump.json", "w") as f:
    json.dump(dump, f, indent=2)

print("Generated memory dump data at /data/dump.json")
print(f"Flag (base64): {FLAG_B64}")
