"""DirCorp — a tiny corporate directory login.

The handler builds an LDAP search filter by interpolating the
username and password into a template, then runs it against an
in-memory directory using a small filter parser. Classic LDAP
injection: an attacker who knows the filter shape can fuse extra
clauses into it and bypass the password check.

Player goal: log in as the admin without knowing the admin password.
"""

import re
from flask import Flask, request, jsonify

app = Flask(__name__)

FLAG = "CTF{REDACTED}"

DIRECTORY = [
    {"uid": "admin", "password": "H4nd3d-D0wn-1n-secret", "role": "admin", "cn": "Site Admin"},
    {"uid": "guest", "password": "guest",                "role": "user",  "cn": "Guest Account"},
    {"uid": "alice", "password": "alice2026",            "role": "user",  "cn": "Alice Ng"},
    {"uid": "bob",   "password": "letmein",              "role": "user",  "cn": "Bob R."},
]


# ---------------------------------------------------------------------------
# Tiny LDAP filter parser. Supports (& ...), (| ...), (! ...), and (attr=val)
# with `*` as a wildcard inside the value.
# ---------------------------------------------------------------------------

def parse(filter_str: str):
    s = filter_str
    node, i = _parse_node(s, 0)
    # Strict — no trailing garbage.
    if i != len(s):
        raise ValueError(f"trailing characters at offset {i}: {s[i:]!r}")
    return node


def _parse_node(s: str, i: int):
    if i >= len(s) or s[i] != "(":
        raise ValueError(f"expected '(' at offset {i}")
    i += 1
    if i >= len(s):
        raise ValueError("truncated filter")
    op = s[i]
    if op in ("&", "|"):
        i += 1
        children = []
        while i < len(s) and s[i] != ")":
            child, i = _parse_node(s, i)
            children.append(child)
        if i >= len(s):
            raise ValueError("missing ')'")
        return ("AND" if op == "&" else "OR", children), i + 1
    if op == "!":
        i += 1
        child, i = _parse_node(s, i)
        if i >= len(s) or s[i] != ")":
            raise ValueError("missing ')' after !")
        return ("NOT", child), i + 1
    # leaf: attr=value up to ")"
    end = s.find(")", i)
    if end < 0:
        raise ValueError("missing ')' on leaf")
    attr, sep, value = s[i:end].partition("=")
    if not sep:
        raise ValueError("leaf missing '='")
    return ("EQ", attr.strip(), value), end + 1


def matches(node, entry: dict) -> bool:
    kind = node[0]
    if kind == "AND":
        return all(matches(c, entry) for c in node[1])
    if kind == "OR":
        return any(matches(c, entry) for c in node[1])
    if kind == "NOT":
        return not matches(node[1], entry)
    if kind == "EQ":
        _, attr, value = node
        actual = entry.get(attr, "")
        if value == "*":
            # "(attr=*)" — present with any non-empty value
            return bool(actual)
        if "*" in value:
            pat = re.escape(value).replace(r"\*", ".*")
            return re.fullmatch(pat, str(actual)) is not None
        return str(actual) == value
    return False


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------

PAGE = """<!doctype html>
<html><head><title>DirCorp</title><style>
body{font-family:system-ui;background:#0c0c18;color:#e8e8e8;padding:32px;max-width:780px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
.muted{color:#888}
</style></head><body>
<h1>DirCorp</h1>
<p class="muted">Corporate directory — login via LDAP-style filter lookup.</p>

<div class="card">
  <strong>Endpoint</strong>
  <pre>
POST /login
Content-Type: application/json

{ "username": "guest", "password": "guest" }

# Server runs (roughly):
#   filter = (&(uid=<USER>)(password=<PASS>))
#   entries = directory.search(filter)
  </pre>
</div>

<div class="card">
  <strong>Hint</strong>
  <p>The filter is built by string interpolation. You know the
  template — what shape do you need to push into it?</p>
</div>
</body></html>"""


@app.route("/")
def home():
    return PAGE


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    user = str(data.get("username", ""))
    pw = str(data.get("password", ""))
    if not user or not pw:
        return jsonify({"error": "username and password required"}), 400
    if len(user) > 128 or len(pw) > 128:
        return jsonify({"error": "too long"}), 400

    # VULNERABLE: direct string interpolation into the filter.
    flt = f"(&(uid={user})(password={pw}))"
    try:
        node = parse(flt)
    except ValueError as exc:
        return jsonify({"error": f"filter parse error: {exc}", "filter": flt}), 400

    hits = [e for e in DIRECTORY if matches(node, e)]
    if not hits:
        return jsonify({"error": "login failed", "filter": flt}), 401

    # If admin is among the hits, hand out the flag.
    for h in hits:
        if h["uid"] == "admin":
            return jsonify({
                "token": "ADMIN-OK",
                "flag": FLAG,
                "filter": flt,
                "matched": [{"uid": x["uid"], "role": x["role"]} for x in hits],
            })
    one = hits[0]
    return jsonify({
        "token": "USER-OK",
        "role": one["role"],
        "cn": one["cn"],
        "filter": flt,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
