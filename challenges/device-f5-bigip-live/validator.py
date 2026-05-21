"""Loopback validator for the F5 BIG-IP live forensics challenge."""

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
            "What unauthenticated path-traversal JSP filename did the "
            "attacker hit through the TMUI to dump files? (Exact JSP "
            "filename — e.g. `someThing.jsp`.)"
        ),
        "hint": (
            "`show httpd-log | include /etc/shadow` — the request "
            "path traverses through `..;/tmui/locallb/workspace/` "
            "to reach a JSP that reads files."
        ),
        "technique": "T1190",
    },
    "2": {
        "prompt": (
            "What is the username of the rogue admin account the "
            "attacker created via TMSH? (Lowercase username only.)"
        ),
        "hint": (
            "`list /auth user` lists every TMSH user. The legit ones "
            "are `admin` and `noc-readonly`."
        ),
        "technique": "T1078",
    },
    "3": {
        "prompt": (
            "What is the name of the iRule that exfiltrates HTTP "
            "headers? (Exact rule name, e.g. `ir_foo_bar`.)"
        ),
        "hint": (
            "`list /ltm rule` — one iRule has a `catch { exec "
            "/bin/logger -n ... }` line. That's the exfil channel."
        ),
        "technique": "T1071.001",
    },
    "4": {
        "prompt": (
            "Which virtual server has the exfiltration iRule "
            "attached? (Exact VS name, e.g. `vs_foo`.)"
        ),
        "hint": (
            "`list /ltm virtual` — look at the `rules { ... }` "
            "block on each VS."
        ),
        "technique": "T1556",
    },
    "5": {
        "prompt": (
            "From which source IP did the attacker exploit the TMUI "
            "RCE? (Format x.x.x.x.)"
        ),
        "hint": (
            "`show httpd-log | include REDACTED` — the unique "
            "source IP behind the traversal requests."
        ),
        "technique": "T1021.001",
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
