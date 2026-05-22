"""CouponStore — a tiny credit-redemption + buy-flag service.

You start with 0 credits. The promo coupon `WELCOME100` adds 100
credits to your balance. It is documented (and intended) as
single-use per-account. The flag costs 1000 credits.

The bug: the redeem handler reads `coupon.used`, sleeps to simulate
slow DB I/O, then increments. The check-and-update is NOT atomic
and NOT locked. Concurrent requests all see `used=0`, all pass the
check, all add 100 to your balance. Race the gap — you bank
enough credits to buy the flag.
"""

import threading
import time
import uuid
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

with open('/opt/flag.txt') as _f:
    FLAG = _f.read().strip()
COUPON_CODE = "WELCOME100"
PROMO_VALUE = 100
FLAG_PRICE = 1000

# Per-session balance. Threadsafe dict-of-int reads/writes inside
# Python's GIL are atomic for assignment, but the *check-then-set*
# pattern in /redeem is not.
BALANCES: dict[str, int] = {}

# Single shared coupon record. Mutated without a lock — that's the
# point of the challenge.
COUPON = {"max_uses": 1, "used": 0}


def session_id() -> str:
    return request.cookies.get("sid") or ""


PAGE = """<!doctype html>
<html><head><title>CouponStore</title><style>
body{font-family:system-ui;background:#0c0c18;color:#e8e8e8;padding:32px;max-width:780px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
.muted{color:#888}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
.bal{font-size:32px;color:#9be59b}
</style></head><body>
<h1>CouponStore</h1>
<p class="muted">redeem promos, buy flags.</p>

<div class="card">
  <div class="muted">your balance</div>
  <div class="bal">{balance} credits</div>
  <div class="muted">session: <code>{sid}</code></div>
</div>

<div class="card">
  <strong>Endpoints</strong>
  <pre>
POST /redeem     { "code": "WELCOME100" }   # single-use per account (allegedly), +100 credits
POST /buy-flag                              # exchanges 1000 credits for the flag
GET  /balance                               # current credit balance for your session
  </pre>
</div>

<div class="card">
  <strong>Promo code</strong>
  <p>Try <code>WELCOME100</code>. It's a single-use welcome bonus.</p>
</div>
</body></html>
"""


@app.route("/")
def home():
    sid = session_id()
    if not sid:
        sid = uuid.uuid4().hex[:16]
    BALANCES.setdefault(sid, 0)
    resp = make_response(PAGE.format(balance=BALANCES[sid], sid=sid))
    resp.set_cookie("sid", sid, httponly=False)
    return resp


@app.route("/balance")
def balance():
    sid = session_id()
    if not sid or sid not in BALANCES:
        return {"balance": 0}
    return {"balance": BALANCES[sid]}


@app.route("/redeem", methods=["POST"])
def redeem():
    sid = session_id()
    if not sid:
        return {"error": "no session — visit / first"}, 400
    BALANCES.setdefault(sid, 0)

    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if code != COUPON_CODE:
        return {"error": "invalid coupon code"}, 400

    # VULNERABLE: classic TOCTOU. Read the counter, simulate a
    # slow DB transaction with a sleep, then update. No mutex.
    if COUPON["used"] >= COUPON["max_uses"]:
        return {"error": "coupon already redeemed"}, 400

    time.sleep(0.25)  # the window

    COUPON["used"] += 1
    BALANCES[sid] += PROMO_VALUE

    return {"ok": True, "added": PROMO_VALUE, "balance": BALANCES[sid]}


@app.route("/buy-flag", methods=["POST"])
def buy_flag():
    sid = session_id()
    if not sid or BALANCES.get(sid, 0) < FLAG_PRICE:
        return {
            "error": f"need {FLAG_PRICE} credits to redeem the flag",
            "balance": BALANCES.get(sid, 0),
        }, 402
    # Don't charge — the player has already done the work.
    return {"flag": FLAG}


if __name__ == "__main__":
    # threaded=True is Flask's dev-server default, but be explicit:
    # the bug only shines when requests are processed concurrently.
    app.run(host="0.0.0.0", port=5000, threaded=True)
