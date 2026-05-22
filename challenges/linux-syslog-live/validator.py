"""Loopback validator for the Linux/RHEL live forensics challenge."""

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
        "prompt": "Source IPv4 of the SSH brute force that eventually succeeded. (Format x.x.x.x.)",
        "hint": "`cat /var/log/secure | include Failed password` and `| include Accepted` share a source.",
        "technique": "T1110",
    },
    "2": {
        "prompt": "Local username the attacker brute-forced and now holds a session as. (Username only.)",
        "hint": "`who` shows the live shells; `cat /var/log/secure | include Accepted` confirms.",
        "technique": "T1078",
    },
    "3": {
        "prompt": "Which SUID binary did the attacker invoke for privilege escalation? (Just the filename, e.g. `foo`.)",
        "hint": "`find / -perm -4000 -type f` lists candidates. `cat /var/log/secure | include sudo` shows what they actually ran.",
        "technique": "T1068",
    },
    "4": {
        "prompt": "Name of the cron file under `/etc/cron.d/` that the attacker added for persistence. (Filename only.)",
        "hint": "`ls /etc/cron.d` — the recent / unfamiliar entry. `cat` it for the body.",
        "technique": "T1053.003",
    },
    "5": {
        "prompt": "Destination IPv4:port the persistence script's reverse shell connects to. (Format x.x.x.x:NNNN.)",
        "hint": "`cat /usr/local/bin/REDACTED.sh` shows the `/dev/tcp/...` redirect; `ss -tnp | include 4444` confirms the live socket.",
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
