"""Loopback validator for the live Cisco IOS forensics challenge.

Same shape as the factory-generated threat-hunt validator — the
`answer` CLI hits this on 127.0.0.1:5000.
"""

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
        "prompt": (
            "What is the username of the rogue privilege-level-15 local "
            "account the attacker added? (Lowercase username only.)"
        ),
        "hint": (
            "`enable` then `show running-config | include privilege` — "
            "compare against the approved roster (cat ~/approved-users.txt)."
        ),
        "technique": "T1078",
    },
    "2": {
        "prompt": (
            "What is the SNMP community string configured with RW "
            "(read-write) access? (Exact string, case-sensitive.)"
        ),
        "hint": (
            "`show snmp` lists them at the bottom; `show running-config | "
            "include snmp-server community` also works."
        ),
        "technique": "T1078.001",
    },
    "3": {
        "prompt": (
            "What is the destination IP of the unauthorised GRE tunnel "
            "the attacker created on Tunnel0? (Format x.x.x.x.)"
        ),
        "hint": (
            "`show running-config | section interface Tunnel0` — look at "
            "the `tunnel destination` line."
        ),
        "technique": "T1133",
    },
    "4": {
        "prompt": (
            "Which ACL number was modified to permit outbound traffic to "
            "the attacker's C2 prefix? (Number only, e.g. 103.)"
        ),
        "hint": (
            "`show access-lists` — look for the list permitting traffic "
            "to REDACTED."
        ),
        "technique": "T1562.004",
    },
    "5": {
        "prompt": (
            "From which source IP did the attacker authenticate to the "
            "vty over SSH? (Format x.x.x.x.)"
        ),
        "hint": (
            "`show users` shows the live vty session; `show logging` "
            "confirms it via SEC_LOGIN-5-LOGIN_SUCCESS."
        ),
        "technique": "T1021.004",
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



def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@app.route("/questions")
def questions():
    return jsonify(
        {qid: {"prompt": q["prompt"], "hint": q["hint"]} for qid, q in QUESTIONS.items()}
    )


@app.route("/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True, silent=True) or {}
    qid = str(data.get("question", "")).strip()
    submitted = data.get("answer", "")
    q = QUESTIONS.get(qid)
    if q is None:
        return jsonify({"error": f"no such question: {qid!r}"}), 404
    correct = _normalise(submitted) == _normalise(q["answer"])
    return jsonify({"question": qid, "correct": correct})


@app.route("/reveal", methods=["POST"])
def reveal():
    data = request.get_json(force=True, silent=True) or {}
    answers = data.get("answers") or {}
    missing, wrong = [], []
    for qid, q in QUESTIONS.items():
        a = answers.get(qid)
        if a is None:
            missing.append(qid)
        elif _normalise(a) != _normalise(q["answer"]):
            wrong.append(qid)
    if missing or wrong:
        return jsonify({"missing": missing, "wrong": wrong}), 400
    return jsonify({"flag": FLAG})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
