"""NetTools — a 'helpful' admin UI that wraps ping / dig / whois.

The handlers `shell-out` to real binaries with the user-supplied host
spliced into the command string. There's a half-hearted blacklist
that strips spaces and a few obvious operators — it doesn't help.

Player goal: pull /flag.txt via shell injection.
"""

import re
import shlex
import subprocess
from flask import Flask, request

app = Flask(__name__)


# Half-hearted blacklist — strips the "obviously dangerous" shell
# operators. Misses command substitution, newline injection, and a
# handful of other sinks. That gap is the lesson.
_FORBIDDEN = re.compile(r"[;|&]")


def cleanse(s: str) -> str:
    """Strip a couple of bad metachars. Still safe? Definitely not."""
    return _FORBIDDEN.sub("", s)


def run(cmd: str) -> str:
    # WHY: shell=True over a string built with user input is the
    # canonical command-injection sink. Bypass surface intentionally
    # broad.
    p = subprocess.run(
        cmd, shell=True, capture_output=True, timeout=8, text=True
    )
    return p.stdout + ("\n[stderr]\n" + p.stderr if p.stderr else "")


PAGE = """<!doctype html>
<html><head><title>NetTools</title><style>
body{font-family:system-ui;background:#0b0b14;color:#ddd;padding:32px;max-width:820px;margin:auto}
h1{color:#7af}
.card{background:#161624;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
input,button{font-family:inherit;padding:8px 12px;background:#0d0d18;color:#eee;border:1px solid #333;border-radius:6px}
button{background:#1e3a8a;border-color:#3b5bff;cursor:pointer}
pre{background:#000;padding:14px;border-radius:6px;overflow-x:auto;color:#9be5a8;max-height:420px}
.muted{color:#888}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
</style></head><body>
<h1>NetTools</h1>
<p class="muted">Quick network diagnostics for the on-call team.</p>

<div class="card">
  <form method="GET" action="/ping">
    <label>Ping host: <input name="host" placeholder="example.com"/></label>
    <button>Run</button>
  </form>
</div>

<div class="card">
  <form method="GET" action="/lookup">
    <label>DNS lookup: <input name="host" placeholder="example.com"/></label>
    <button>Run</button>
  </form>
</div>

<div class="card">
  <strong>Endpoints</strong>
  <pre>
GET /ping?host=&lt;hostname&gt;     # 4 ICMP echos
GET /lookup?host=&lt;hostname&gt;   # dig A record
GET /whois?host=&lt;hostname&gt;    # admin only
  </pre>
</div>
</body></html>
"""


@app.route("/")
def home():
    return PAGE


@app.route("/ping")
def ping():
    raw = request.args.get("host", "").strip()
    if not raw:
        return {"error": "host param required"}, 400
    # Intentionally weak: cleanse() is the only defence and it
    # misses, e.g. newline escape sequences, backslash-zero etc.
    host = cleanse(raw)[:128]
    out = run(f"ping -c 2 -W 2 {host}")
    return f"<pre>$ ping -c 2 -W 2 {host}\n{out}</pre>"


@app.route("/lookup")
def lookup():
    raw = request.args.get("host", "").strip()
    if not raw:
        return {"error": "host param required"}, 400
    host = cleanse(raw)[:128]
    out = run(f"dig +short A {host}")
    return f"<pre>$ dig +short A {host}\n{out}</pre>"


@app.route("/whois")
def whois():
    if request.headers.get("X-Role") != "admin":
        return {"error": "admin only"}, 403
    raw = request.args.get("host", "").strip()
    host = shlex.quote(raw)
    out = run(f"echo whois {host} would run here")
    return f"<pre>{out}</pre>"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
