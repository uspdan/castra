"""Loopback validator for the pfSense live challenge."""

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
        "prompt": "What is the username of the rogue admin account added via the WebGUI? (Lowercase username only.)",
        "hint": "`show users` — three users. Two belong; one was added with a `fullname` carrying a recent timestamp.",
        "technique": "T1078",
    },
    "2": {
        "prompt": "From which source IP did the attacker successfully authenticate to the WebGUI? (Format x.x.x.x.)",
        "hint": "`show auth-log | include authenticated successfully` — same IP that previously had 200+ failures.",
        "technique": "T1110",
    },
    "3": {
        "prompt": "What is the description (`descr`) of the rogue NAT rule? (Exact value as it appears in the config.)",
        "hint": "`show config | begin <nat>` shows the rule block — the `<descr>` field.",
        "technique": "T1133",
    },
    "4": {
        "prompt": "What is the internal target IP the rogue NAT rule forwards to? (Format x.x.x.x.)",
        "hint": "`show nat` — the `rdr on em0 ... -> <IP> port 22` line.",
        "technique": "T1021.004",
    },
    "5": {
        "prompt": "What WAN port does the rogue NAT rule listen on? (Port number only.)",
        "hint": "Same `show nat` line — the `port = <PORT>` before the `->`.",
        "technique": "T1133",
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
