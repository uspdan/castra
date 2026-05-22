"""Loopback validator for the Cisco IOS XE CVE-2023-20198 challenge."""

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
            "What is the username of the rogue privilege-15 local user "
            "the WebUI bypass created? (Lowercase username only.)"
        ),
        "hint": (
            "`enable`, then `show running-config | include privilege 15`. "
            "Compare to ~/approved-users.txt."
        ),
        "technique": "T1078",
    },
    "2": {
        "prompt": (
            "What is the source IP of the WebUI exploit traffic? "
            "(Format x.x.x.x.)"
        ),
        "hint": "`show webui-log` — only one external IP hits the /webui/ paths.",
        "technique": "T1190",
    },
    "3": {
        "prompt": (
            "What URL-encoded path did the attacker POST to in order "
            "to invoke the WSMA bypass? (Exact path as it appears in "
            "the WebUI access log.)"
        ),
        "hint": (
            "`show webui-log` — the second request contains a `%25` "
            "URL-double-encoding trick to reach the WSMA handler."
        ),
        "technique": "T1190",
    },
    "4": {
        "prompt": (
            "What TCP port is the Lua implant listening on inside the "
            "router? (Port number only.)"
        ),
        "hint": (
            "`show ip http server status` — the bottom section lists "
            "an extra nginx-bound port from a custom module."
        ),
        "technique": "T1505.003",
    },
    "5": {
        "prompt": (
            "What is the process name that the implant runs as on "
            "Forwarding Plane 0? (Exact `Name` column value from "
            "`show platform software process list`.)"
        ),
        "hint": (
            "`show platform software process list` — one process name "
            "doesn't belong to a stock IOS XE image."
        ),
        "technique": "T1505.003",
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
    if q is None:
        return jsonify({"error": f"no such question: {qid!r}"}), 404
    return jsonify({"question": qid, "correct": _normalise(data.get("answer", "")) == _normalise(q["answer"])})


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
