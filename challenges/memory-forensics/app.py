"""Memory Forensics Challenge - Simulated Volatility-like interface."""

import json
import base64
from flask import Flask, request, render_template_string

app = Flask(__name__)

with open("/data/dump.json") as f:
    DUMP = json.load(f)

with open('/opt/flag.txt') as _f:
    FLAG = _f.read().strip()
HELP_TEXT = """Available commands:
  pslist          - List running processes
  netscan         - Show network connections
  strings <pid>   - Extract strings from process memory
  procdump <pid>  - Dump process executable info
  malfind         - Scan for injected code / suspicious memory regions
  help            - Show this help

Analyze the memory dump to find the suspicious process and extract the flag."""

HTML = """<!DOCTYPE html>
<html>
<head>
<title>Memory Forensics Lab</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: monospace; background: #0a0a0a; color: #e0e0e0; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
.container { background: #1a1a1a; padding: 30px; border-radius: 8px; width: 800px; border: 1px solid #333; }
h1 { color: #00c8ff; margin-bottom: 16px; font-size: 20px; text-align: center; }
.terminal { background: #000; border: 1px solid #333; border-radius: 4px; padding: 16px; margin-bottom: 16px; min-height: 400px; max-height: 600px; overflow-y: auto; white-space: pre-wrap; font-size: 13px; line-height: 1.5; }
.prompt { color: #00e5a0; }
.output { color: #c0c0c0; }
.error { color: #ff3e6c; }
.flag { color: #f0b429; font-weight: bold; }
form { display: flex; gap: 8px; }
input { flex: 1; padding: 10px; background: #0a0a0a; border: 1px solid #333; border-radius: 4px; color: #e0e0e0; font-family: monospace; }
button { padding: 10px 20px; background: #00c8ff; color: #0a0a0a; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; font-family: monospace; }
</style>
</head>
<body>
<div class="container">
    <h1>Volatility Memory Analyzer</h1>
    <div class="terminal">
        <span class="prompt">vol3></span> <span class="output">{{ command }}</span>
<span class="{{ output_class }}">{{ output }}</span>
    </div>
    <form method="POST">
        <input type="text" name="command" placeholder="Enter command (type 'help' for usage)" autofocus>
        <button type="submit">Run</button>
    </form>
</div>
</body>
</html>"""


def format_pslist():
    header = f"{'PID':<8}{'PPID':<8}{'Name':<25}{'User':<25}{'Thds':<6}{'Hnds':<8}{'Start Time'}"
    lines = [header, "-" * len(header)]
    for p in DUMP["process_list"]:
        lines.append(
            f"{p['pid']:<8}{p['ppid']:<8}{p['name']:<25}{p['user']:<25}"
            f"{p['threads']:<6}{p['handles']:<8}{p['start_time']}"
        )
    return "\n".join(lines)


def format_netscan():
    header = f"{'PID':<8}{'Process':<25}{'Local Address':<25}{'Remote Address':<25}{'State':<15}{'Proto'}"
    lines = [header, "-" * len(header)]
    for c in DUMP["network_connections"]:
        local = f"{c['local_addr']}:{c['local_port']}"
        remote = f"{c['remote_addr']}:{c['remote_port']}"
        lines.append(
            f"{c['pid']:<8}{c['name']:<25}{local:<25}{remote:<25}{c['state']:<15}{c['protocol']}"
        )
    return "\n".join(lines)


def format_strings(pid_str):
    if pid_str not in DUMP["strings"]:
        return f"No strings found for PID {pid_str}"
    strings = DUMP["strings"][pid_str]
    lines = [f"Strings for PID {pid_str}:", "-" * 40]
    for s in strings:
        try:
            decoded = base64.b64decode(s).decode()
            if decoded.startswith("CTF{REDACTED}  (decoded: {decoded})")
                continue
        except Exception:
            pass
        lines.append(f"  {s}")
    return "\n".join(lines)


def format_procdump(pid_str):
    pid = int(pid_str) if pid_str.isdigit() else -1
    proc = next((p for p in DUMP["process_list"] if p["pid"] == pid), None)
    if not proc:
        return f"Process with PID {pid_str} not found"
    lines = [
        f"Process Dump for PID {pid}:",
        f"  Name:       {proc['name']}",
        f"  PID:        {proc['pid']}",
        f"  PPID:       {proc['ppid']}",
        f"  User:       {proc['user']}",
        f"  Threads:    {proc['threads']}",
        f"  Handles:    {proc['handles']}",
        f"  Start Time: {proc['start_time']}",
    ]
    if pid == 4892:
        lines.extend([
            "",
            "  [!] SUSPICIOUS INDICATORS:",
            "  - Process name mimics system process (svchost)",
            "  - Running from user Temp directory",
            "  - Parent is explorer.exe (not services.exe)",
            f"  - Connections to suspicious IP: 185.141.27.3",
        ])
    return "\n".join(lines)


def format_malfind():
    lines = [
        "Scanning for suspicious memory regions...",
        "",
        "PID 4892 (svchost_update.exe):",
        "  VAD Tag: VadS  Protection: PAGE_EXECUTE_READWRITE",
        "  Address: 0x00400000  Size: 0x3000",
        "  Flags: CommitCharge: 3, MemCommit, PrivateMemory",
        "  [!] Executable code in suspicious location",
        "  [!] Contains API hashing shellcode pattern",
        "",
        "  Suspicious API imports detected:",
        "    - VirtualAlloc / VirtualProtect",
        "    - CreateRemoteThread",
        "    - NtQueryInformationProcess",
        "",
        "  Recommendation: Run 'strings 4892' to examine embedded strings",
        "",
        "No other suspicious regions found.",
    ]
    return "\n".join(lines)


@app.route("/", methods=["GET", "POST"])
def index():
    command = ""
    output = HELP_TEXT
    output_class = "output"

    if request.method == "POST":
        command = request.form.get("command", "").strip()
        parts = command.split()
        cmd = parts[0].lower() if parts else ""
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "help":
            output = HELP_TEXT
        elif cmd == "pslist":
            output = format_pslist()
        elif cmd == "netscan":
            output = format_netscan()
        elif cmd == "strings":
            if not arg:
                output = "Usage: strings <pid>"
                output_class = "error"
            else:
                output = format_strings(arg)
                if "CTF{REDACTED}. Type 'help' for available commands."
            output_class = "error"

    return render_template_string(
        HTML, command=command, output=output, output_class=output_class
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
