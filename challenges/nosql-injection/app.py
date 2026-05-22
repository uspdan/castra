"""DocVault — a tiny login page backed by a Mongo-style document
store.

The login handler reads the JSON body and hands the entire dict
straight into a "Mongo-like" query function. The query function
supports the usual operators ($ne, $gt, $regex, $in). Real
MongoDB clients do exactly this when the app forgets to coerce
incoming values to strings.

Player goal: log in as admin without knowing admin's password.
"""

import re
from flask import Flask, request, jsonify

app = Flask(__name__)

with open('/opt/flag.txt') as _f:
    FLAG = _f.read().strip()
# Admin is intentionally first — so any "match-anything" bypass
# hits admin before it hits guest.
USERS = [
    {"username": "admin", "password": "9c8f3a-r0t4t3d-Z!", "role": "admin"},
    {"username": "alice", "password": "alice2026",         "role": "user"},
    {"username": "bob",   "password": "letmein",           "role": "user"},
    {"username": "guest", "password": "guest",             "role": "user"},
]


def match_value(actual, criterion):
    """Compare a document field against a Mongo-style criterion."""
    if isinstance(criterion, dict):
        for op, val in criterion.items():
            if op == "$ne":
                if actual == val:
                    return False
            elif op == "$gt":
                try:
                    if not (actual > val):
                        return False
                except TypeError:
                    return False
            elif op == "$lt":
                try:
                    if not (actual < val):
                        return False
                except TypeError:
                    return False
            elif op == "$in":
                if not isinstance(val, list) or actual not in val:
                    return False
            elif op == "$regex":
                if not isinstance(val, str):
                    return False
                if re.search(val, str(actual)) is None:
                    return False
            elif op == "$exists":
                if bool(val) is not (actual is not None):
                    return False
            else:
                # Unknown operator. Fail closed for that clause.
                return False
        return True
    # Scalar/equality
    return actual == criterion


def query(filter_doc, collection):
    out = []
    for doc in collection:
        if all(match_value(doc.get(k), v) for k, v in filter_doc.items()):
            out.append(doc)
    return out


PAGE = """<!doctype html>
<html><head><title>DocVault</title><style>
body{font-family:system-ui;background:#0c0c18;color:#e8e8e8;padding:32px;max-width:760px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
.muted{color:#888}
</style></head><body>
<h1>DocVault</h1>
<p class="muted">A login page on top of a Mongo-style document store.</p>

<div class="card">
<strong>Endpoint</strong>
<pre>
POST /login
Content-Type: application/json

{ "username": "guest", "password": "guest" }

# Server runs (roughly):
#   users.find({"username": &lt;BODY.username&gt;, "password": &lt;BODY.password&gt;})
</pre>
</div>

<div class="card">
<strong>Hint</strong>
<p>Body values go in untouched. The query layer understands
   operators.</p>
</div>
</body></html>"""


@app.route("/")
def home():
    return PAGE


@app.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    if "username" not in body or "password" not in body:
        return jsonify({"error": "username and password required"}), 400
    # VULNERABLE: the body's values pass into the query verbatim —
    # operator dicts and all.
    flt = {"username": body["username"], "password": body["password"]}
    hits = query(flt, USERS)
    if not hits:
        return jsonify({"error": "login failed", "filter": flt}), 401
    first = hits[0]
    out = {"username": first["username"], "role": first["role"]}
    if first["role"] == "admin":
        out["flag"] = FLAG
    return jsonify(out)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
