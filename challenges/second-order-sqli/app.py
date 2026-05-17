"""AccountVault — register, login, change your password.

Registration uses a parameterised INSERT, so any username — even
one with embedded quotes — is stored verbatim. The
change-password handler reads the user's stored username back
from the DB and **interpolates it** into the UPDATE query.

That second hop is where the SQL injection lands. Classic
"second-order" SQLi: the input was sanitised at write time, but
trusted at read time.

Player goal: take over the `admin` account and hit /admin/flag.
"""

import os
import sqlite3
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)

DB = "/tmp/accountvault.db"
FLAG = "CTF{REDACTED}"

# Token -> account row id. In-memory; fresh per container.
SESSIONS: dict[str, int] = {}


def init_db():
    if os.path.exists(DB):
        os.remove(DB)
    db = sqlite3.connect(DB)
    db.executescript("""
        CREATE TABLE users (
            id        INTEGER PRIMARY KEY,
            username  TEXT UNIQUE NOT NULL,
            password  TEXT NOT NULL,
            role      TEXT NOT NULL DEFAULT 'user'
        );
        INSERT INTO users (username, password, role)
        VALUES ('admin', 'r0t4t3d-r4nd0m-9c2f', 'admin');
    """)
    db.commit()
    db.close()


def conn():
    return sqlite3.connect(DB)


PAGE = """<!doctype html>
<html><head><title>AccountVault</title><style>
body{font-family:system-ui;background:#0c0c18;color:#e8e8e8;padding:32px;max-width:780px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
.muted{color:#888}
</style></head><body>
<h1>AccountVault</h1>
<p class="muted">Register, login, manage your password. Admin runs the audit panel.</p>

<div class="card">
<strong>Endpoints</strong>
<pre>
POST /register          { "username": "...", "password": "..." }
POST /login             { "username": "...", "password": "..." } -> { "token": "..." }
POST /change-password   { "new_password": "..." }   Authorization: Bearer &lt;token&gt;
GET  /admin/flag                                    Authorization: Bearer &lt;admin token&gt;
</pre>
</div>

<div class="card">
<strong>Hint</strong>
<p>Registration is parameterised. Other endpoints, maybe not.</p>
</div>
</body></html>"""


@app.route("/")
def home():
    return PAGE


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    u = (data.get("username") or "").strip()
    p = (data.get("password") or "").strip()
    if not u or not p:
        return jsonify({"error": "username and password required"}), 400
    if len(u) > 64 or len(p) > 64:
        return jsonify({"error": "too long"}), 400
    db = conn()
    try:
        # SAFE: parameterised. Anything goes in the username field,
        # quotes included.
        db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (u, p))
        db.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "username taken"}), 409
    finally:
        db.close()
    return jsonify({"ok": True, "username": u})


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    u = (data.get("username") or "").strip()
    p = (data.get("password") or "").strip()
    db = conn()
    row = db.execute(
        "SELECT id, role FROM users WHERE username = ? AND password = ?",
        (u, p),
    ).fetchone()
    db.close()
    if not row:
        return jsonify({"error": "bad credentials"}), 401
    token = uuid.uuid4().hex
    SESSIONS[token] = row[0]
    return jsonify({"token": token, "role": row[1]})


def auth_uid():
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        return None
    return SESSIONS.get(h[7:])


@app.route("/change-password", methods=["POST"])
def change_password():
    uid = auth_uid()
    if uid is None:
        return jsonify({"error": "unauthenticated"}), 401
    new_pw = (request.get_json(silent=True) or {}).get("new_password", "")
    if not new_pw:
        return jsonify({"error": "new_password required"}), 400

    db = conn()
    # Look up the caller's stored username — this is the value
    # that was sanitised when written, but is about to be trusted.
    row = db.execute("SELECT username FROM users WHERE id = ?", (uid,)).fetchone()
    stored_username = row[0]

    # VULNERABLE: stored_username is interpolated into the UPDATE.
    # An attacker who registered with a quote-bearing username
    # gets to control the WHERE clause.
    query = (
        f"UPDATE users SET password = '{new_pw}' "
        f"WHERE username = '{stored_username}'"
    )
    db.executescript(query)
    db.commit()
    db.close()
    return jsonify({
        "ok": True,
        "executed": query,
    })


@app.route("/admin/flag", methods=["GET"])
def admin_flag():
    uid = auth_uid()
    if uid is None:
        return jsonify({"error": "unauthenticated"}), 401
    db = conn()
    row = db.execute("SELECT role FROM users WHERE id = ?", (uid,)).fetchone()
    db.close()
    if not row or row[0] != "admin":
        return jsonify({"error": "admin only"}), 403
    return jsonify({"flag": FLAG})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)
