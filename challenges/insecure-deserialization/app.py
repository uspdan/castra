"""DiaryBox — a tiny journal app with a 'remember-me' cookie.

The remember-me cookie is a base64-encoded Python pickle of the user's
profile. Reload your session on every request without touching the
server-side session store! Convenient. Also: classic pickle RCE sink.

Player goal: forge a remember-me cookie that executes arbitrary code
on the server when the app rehydrates it, then exfiltrate /flag.txt.
"""

import base64
import io
import os
import pickle
from flask import Flask, request, make_response

app = Flask(__name__)
COOKIE_NAME = "diarybox_user"


class GuestProfile:
    def __init__(self, name="guest", theme="dark", note_count=0):
        self.name = name
        self.theme = theme
        self.note_count = note_count

    def display(self):
        return f"{self.name} (theme={self.theme}, {self.note_count} notes)"


def encode_profile(profile) -> str:
    return base64.b64encode(pickle.dumps(profile)).decode()


def decode_profile(raw: str):
    # WHY: pickle.loads on attacker-controlled bytes — the whole point
    # of the challenge. Restricting it would defeat the lesson.
    return pickle.loads(base64.b64decode(raw))


HOME_HTML = """<!doctype html>
<html><head><title>DiaryBox</title>
<style>
body{{font-family:system-ui;background:#111;color:#eee;padding:32px;max-width:720px;margin:auto}}
h1{{color:#7af}}
.card{{background:#1d1d27;padding:20px;border-radius:10px;margin:20px 0;border:1px solid #333}}
code{{background:#000;padding:2px 6px;border-radius:3px;color:#fa6}}
pre{{background:#000;padding:14px;border-radius:6px;overflow-x:auto;color:#ccc}}
.muted{{color:#888}}
</style></head><body>
<h1>DiaryBox</h1>
<p class="muted">a tiny journal app — remember-me cookie edition.</p>

<div class="card">
  <strong>Welcome, {who}.</strong>
  <p>Your profile re-hydrates automatically from the
  <code>{cookie}</code> cookie on every request — no server-side
  session, no Redis, no fuss. Convenient!</p>
</div>

<div class="card">
  <strong>Endpoints</strong>
  <pre>
GET  /           — this page; rehydrates from the remember-me cookie
GET  /whoami     — returns the rehydrated profile as JSON
POST /login      — body: {{"name": "..."}} — re-bakes the cookie
GET  /admin/audit — admin-only audit panel (requires admin profile)
  </pre>
</div>

<div class="card">
  <strong>Hint</strong>
  <p>The cookie is base64. Inside is... well, look.</p>
</div>
</body></html>
"""


def current_profile():
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return GuestProfile()
    try:
        return decode_profile(raw)
    except Exception:
        return GuestProfile()


@app.route("/")
def home():
    prof = current_profile()
    who = prof.display() if hasattr(prof, "display") else str(prof)
    return HOME_HTML.format(who=who, cookie=COOKIE_NAME)


@app.route("/whoami")
def whoami():
    prof = current_profile()
    return {
        "name": getattr(prof, "name", str(prof)),
        "theme": getattr(prof, "theme", None),
        "note_count": getattr(prof, "note_count", 0),
    }


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "guest").strip()[:32]
    profile = GuestProfile(name=name, theme="dark", note_count=0)
    resp = make_response({"ok": True, "name": name})
    resp.set_cookie(COOKIE_NAME, encode_profile(profile), httponly=False)
    return resp


@app.route("/admin/audit")
def admin_audit():
    prof = current_profile()
    if getattr(prof, "name", "") != "admin":
        return {"error": "admin only"}, 403
    return {"audit": "no recent events"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
