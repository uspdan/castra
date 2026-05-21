"""Loopback validator for the Citrix NetScaler live forensics challenge."""

import re
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
            "What URL path did the attacker POST to for the initial "
            "unauthenticated RCE? (Exact path, e.g. `/foo/bar`.)"
        ),
        "hint": (
            "`show httpaccess | include POST` — there are repeated "
            "POSTs against a Gateway endpoint from the attacker IP "
            "immediately before the webshell drop."
        ),
        "technique": "T1190",
    },
    "2": {
        "prompt": (
            "What is the filename of the webshell the attacker "
            "dropped under `/var/netscaler/logon/themes/`? "
            "(Filename only, e.g. `foo.php`.)"
        ),
        "hint": (
            "`show httpaccess | include logon/themes` shows every "
            "GET against it; `show ns log | include GUI cmd` confirms "
            "the file creation."
        ),
        "technique": "T1505.003",
    },
    "3": {
        "prompt": (
            "What is the username of the rogue system user the "
            "attacker added with superuser binding? (Lowercase.)"
        ),
        "hint": (
            "`show system user` and compare; or `show ns log | "
            "include add system user`."
        ),
        "technique": "T1078",
    },
    "4": {
        "prompt": (
            "From which source IP did the attacker exploit the "
            "Gateway and access the webshell? (Format x.x.x.x.)"
        ),
        "hint": (
            "`show httpaccess | include webshell` — same IP behind "
            "every request to the dropped file."
        ),
        "technique": "T1021.001",
    },
    "5": {
        "prompt": (
            "Which load-balancing virtual server did the attacker "
            "create / configure to expose a backend service on "
            "TCP/22 to the internet? (Exact VS name, e.g. `vs_foo`.)"
        ),
        "hint": (
            "`show vserver` lists them — one is on port 22 against "
            "an internal target. `show running config | include "
            "vs_lb_internal` confirms."
        ),
        "technique": "T1133",
    },
}


# Answers are not committed to the public source. The challenge
# container's Dockerfile copies ``secrets/answers/validators/<slug>.json``
# (gitignored) to ``/opt/answers.json`` at build time, and the
# loader below merges them into QUESTIONS before the validator
# starts serving.
import json as _json
import os as _os

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
