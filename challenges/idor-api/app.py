"""NotesVault — a private-notes REST API.

Endpoints check that you're authenticated (a bearer token). They do
NOT check that the authenticated user is the OWNER of the resource
they're asking for. Classic OWASP API #1 — Broken Object Level
Authorization.

Player goal: log in as the throwaway 'guest' user, then read the
admin's private note containing the flag.
"""

from flask import Flask, request, jsonify

app = Flask(__name__)

# Static demo dataset. The flag is inside admin's note #1.
USERS = {
    "guest":  {"id": 7,    "password": "guest",      "role": "user"},
    "alice":  {"id": 12,   "password": "alice2026",  "role": "user"},
    "bob":    {"id": 19,   "password": "letmein",    "role": "user"},
    "admin":  {"id": 1001, "password": "<unknown>",  "role": "admin"},
}

NOTES = {
    7:    [{"id": 101, "title": "todo",            "body": "wash car"}],
    12:   [{"id": 201, "title": "groceries",       "body": "kale, oats"}],
    19:   [{"id": 301, "title": "passwords",       "body": "see 1password"}],
    1001: [
        {"id": 901, "title": "incident-handover",
         "body": "Flag rotation key: CTF{REDACTED}"},
        {"id": 902, "title": "ops-runbook",
         "body": "Restart sequence: db -> cache -> api"},
    ],
}

# Token format: t-<userid>. Issued at login. The API only checks
# "is this token shape valid" — never "does this user own the
# resource being requested".
TOKENS = {}


def issue_token(user_id: int) -> str:
    tok = f"t-{user_id}"
    TOKENS[tok] = user_id
    return tok


def auth_user():
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        return None
    tok = h[7:]
    return TOKENS.get(tok)


@app.route("/")
def home():
    return """<!doctype html>
<html><head><title>NotesVault</title><style>
body{font-family:system-ui;background:#0d0d18;color:#e4e4e4;padding:32px;max-width:780px;margin:auto}
h1{color:#7af}
.card{background:#15152a;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
.muted{color:#888}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
</style></head><body>
<h1>NotesVault</h1>
<p class="muted">A private-notes REST API. Log in, list your notes, read by ID.</p>

<div class="card">
<strong>Endpoints</strong>
<pre>
POST /api/login                          { "username": "...", "password": "..." } -> { "token": "t-..." }
GET  /api/me                             # current user
GET  /api/users/&lt;user_id&gt;/notes          # list notes for &lt;user_id&gt;
GET  /api/users/&lt;user_id&gt;/notes/&lt;nid&gt;     # fetch one note
</pre>
</div>

<div class="card">
<strong>Demo credentials</strong>
<pre>
guest / guest
alice / alice2026
bob   / letmein
</pre>
<p class="muted">There is also an admin user but its password is not yours.</p>
</div>
</body></html>"""


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    u = data.get("username", "")
    p = data.get("password", "")
    rec = USERS.get(u)
    if not rec or rec["password"] != p:
        return jsonify({"error": "bad credentials"}), 401
    return jsonify({"token": issue_token(rec["id"]), "user_id": rec["id"], "role": rec["role"]})


@app.route("/api/me")
def api_me():
    uid = auth_user()
    if uid is None:
        return jsonify({"error": "unauthenticated"}), 401
    # Reverse lookup just for prettiness.
    name = next((n for n, r in USERS.items() if r["id"] == uid), "?")
    return jsonify({"user_id": uid, "username": name})


@app.route("/api/users/<int:user_id>/notes")
def api_list_notes(user_id):
    # BUG (the lesson): we check "is the caller authenticated" but
    # NOT "is the caller the owner of user_id". Any logged-in user
    # can read any other user's notes by guessing/iterating the ID.
    caller = auth_user()
    if caller is None:
        return jsonify({"error": "unauthenticated"}), 401
    return jsonify({"notes": NOTES.get(user_id, [])})


@app.route("/api/users/<int:user_id>/notes/<int:note_id>")
def api_get_note(user_id, note_id):
    caller = auth_user()
    if caller is None:
        return jsonify({"error": "unauthenticated"}), 401
    for n in NOTES.get(user_id, []):
        if n["id"] == note_id:
            return jsonify(n)
    return jsonify({"error": "not found"}), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
