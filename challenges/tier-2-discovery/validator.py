"""Loopback validator for Tier 2: Discovery (tier-2-discovery).

Factory-generated. The canonical answers are baked in below. Listens
on 127.0.0.1:5000 inside the challenge container — only reachable
from within (the orchestrator publishes only the SSH port).
"""

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
        "prompt": "Which built-in Windows binary did the attacker use to list\nthe domain controllers? (Just the filename, e.g. foo.exe.)",
        "hint": "Look for arguments like /dclist.",
        "technique": "T1018"
    },
    "2": {
        "prompt": "What file extension was the attacker hunting for in the\nrecursive find? (Format: .ext, including the dot.)",
        "hint": "A dir /s or where invocation with a *.* pattern.",
        "technique": "T1083"
    },
    "3": {
        "prompt": "What AD group did the attacker enumerate for membership?\n(Exact name as passed to net group, no quotes.)",
        "hint": "net group has the group name as its first argument.",
        "technique": "T1087.002"
    },
    "4": {
        "prompt": "Which AV/EDR product name appeared in the tasklist output\nthe attacker dumped to disk? (Vendor product name as it\nshows in Image Name \u2014 lowercase, e.g. `REDACTED`.)",
        "hint": "Sysmon FileCreate of a .txt artefact; inside, look for\nany process from a known EDR vendor.",
        "technique": "T1057"
    },
    "5": {
        "prompt": "Which remote hostname did the attacker enumerate shares on\nimmediately before moving sideways? (Hostname only, no UNC,\nuppercase.)",
        "hint": "net view \\\\HOSTNAME /all.",
        "technique": "T1135"
    }
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
        if a is None or a == "":
            missing.append(qid)
        elif _normalise(a) != _normalise(q["answer"]):
            wrong.append(qid)

    if missing or wrong:
        return jsonify(
            {
                "correct": False,
                "missing": missing,
                "wrong": wrong,
                "message": "Flag is revealed only when every answer is correct.",
            }
        )

    return jsonify({"correct": True, "flag": FLAG})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
