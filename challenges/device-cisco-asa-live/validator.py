"""Loopback validator for the Cisco ASA / AnyConnect live challenge."""

import re
import os as _os
from flask import Flask, jsonify, request

app = Flask(__name__)
# Flag is not committed to the public source. The challenge container's
# Dockerfile copies a sealed flag file (gitignored, root-owned mode 0600)
# to /opt/flag.txt at build time, and we read it here.
_FLAG_PATH = _os.environ.get("SIEGE_FLAG_PATH", "/opt/flag.txt")
try:
    with open(_FLAG_PATH) as _fh:
        FLAG = _fh.read().strip()
except FileNotFoundError:
    FLAG = ""
QUESTIONS = {
    "1": {
        "prompt": "Which tunnel-group name has MFA disabled on its default group-policy? (Exact tunnel-group name as it appears in the config.)",
        "hint": "`show run | begin group-policy gp_` — one of them carries `anyconnect mfa disable`. Walk back from that group-policy to the tunnel-group that references it.",
        "technique": "T1556.006",
    },
    "2": {
        "prompt": "Which authentication server group is bound to that tunnel-group? (Exact value as it appears after `authentication-server-group`.)",
        "hint": "`show run | begin tunnel-group REDACTED` — the line right under `general-attributes`.",
        "technique": "T1078",
    },
    "3": {
        "prompt": "What VPN username eventually logged in successfully? (Lowercase username only — no domain.)",
        "hint": "`show vpn-sessiondb anyconnect` — two active sessions; one is from the contractor tunnel-group.",
        "technique": "T1078",
    },
    "4": {
        "prompt": "From which public source IP did the attacker brute-force and then connect? (Format x.x.x.x.)",
        "hint": "`show logging | include AAA login failure` — same source IP for 200+ failures and the eventual success.",
        "technique": "T1110",
    },
    "5": {
        "prompt": "What internal IP did the attacker hit over TCP/3389 after the VPN auth succeeded? (Format x.x.x.x.)",
        "hint": "`show logging | include 302013` — the `Built inbound TCP connection` line shows source/dest after VPN landing.",
        "technique": "T1021.001",
    },
}


# Answers are not committed to the public source. The challenge
# container's Dockerfile copies ``secrets/answers/validators/<slug>.json``
# (gitignored) to ``/opt/answers.json`` at build time, and the
# loader below merges them into QUESTIONS before the validator
# starts serving.
import json as _json

_ANSWERS_PATH = _os.environ.get("SIEGE_ANSWERS_PATH", "/opt/answers.json")
try:
    with open(_ANSWERS_PATH) as _fh:
        _SEALED_ANSWERS = _json.load(_fh)
except FileNotFoundError:
    _SEALED_ANSWERS = {}

for _qid, _val in (_SEALED_ANSWERS or {}).items():
    if _qid in QUESTIONS:
        QUESTIONS[_qid]["answer"] = _val



def _normalise(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@app.route("/questions")
def questions():
    return jsonify({qid: {"prompt": q["prompt"], "hint": q["hint"]} for qid, q in QUESTIONS.items()})


@app.route("/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True, silent=True) or {}
    qid = str(data.get("question", "")).strip()
    q = QUESTIONS.get(qid)
    if q is None: return jsonify({"error": f"no such question: {qid!r}"}), 404
    return jsonify({"question": qid, "correct": _normalise(data.get("answer", "")) == _normalise(q["answer"])})


@app.route("/reveal", methods=["POST"])
def reveal():
    data = request.get_json(force=True, silent=True) or {}
    answers = data.get("answers") or {}
    missing, wrong = [], []
    for qid, q in QUESTIONS.items():
        a = answers.get(qid)
        if a is None: missing.append(qid)
        elif _normalise(a) != _normalise(q["answer"]): wrong.append(qid)
    if missing or wrong: return jsonify({"missing": missing, "wrong": wrong}), 400
    return jsonify({"flag": FLAG})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
