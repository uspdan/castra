"""Loopback validator for the Juniper Junos live challenge."""

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
        "prompt": "What is the username of the rogue super-user account added to /system/login? (Lowercase username only.)",
        "hint": "`show configuration | display set | match login` and compare against the legitimate roster (netops, monitor).",
        "technique": "T1078",
    },
    "2": {
        "prompt": "What is the source IP from which the attacker SSHed in as `netops`? (Format x.x.x.x.)",
        "hint": "`show log messages | match Accepted password` or `show system users` — there's a second `netops` session from a non-corp IP.",
        "technique": "T1078",
    },
    "3": {
        "prompt": "What is the sequence number of the commit that landed the malicious changes? (Number only.)",
        "hint": "`show system commit` — the most recent entry shows the user, the verb, and the sequence.",
        "technique": "T1556",
    },
    "4": {
        "prompt": "What is the name of the security policy that was widened to permit traffic toward the attacker's prefix? (Exact policy name as it appears in the config.)",
        "hint": "`show security policies` — one policy lists multiple destination-addresses including an address-book entry called `attacker-c2`.",
        "technique": "T1562.004",
    },
    "5": {
        "prompt": "What CIDR is the `attacker-c2` global address-book entry pointing at? (Format x.x.x.x/yy.)",
        "hint": "`show configuration | display set | match address-book` — the `attacker-c2` entry maps to a /24.",
        "technique": "T1071.001",
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
