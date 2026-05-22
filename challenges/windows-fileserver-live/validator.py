"""Loopback validator for the Windows file-server pre-ransomware challenge."""

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
        "prompt": "Source IPv4 address of the attacker's lateral logon to this file server. (Format x.x.x.x.)",
        "hint": "`Get-WinEvent -LogName REDACTED | include 4624` — type-3 (network) logon's Source Network Address.",
        "technique": "T1021.002",
    },
    "2": {
        "prompt": "SamAccountName under which the lateral logon succeeded. (Lowercase, no domain prefix.)",
        "hint": "Same 4624 line — Account Name.",
        "technique": "T1078",
    },
    "3": {
        "prompt": "What is the full command-line the attacker ran to delete the volume shadow copies? (Including arguments — match the CommandLine field verbatim.)",
        "hint": "`Get-WinEvent -LogName REDACTED | include vssadmin` or `Get-WinEvent -LogName Sysmon | include vssadmin` — the EventID 1 / 4688 CommandLine.",
        "technique": "T1490",
    },
    "4": {
        "prompt": "Name of the service the attacker installed for persistence. (Exact ServiceName.)",
        "hint": "`Get-WinEvent -LogName REDACTED | include 4697` (service installed) or `Get-Service` — one entry has a non-stock display name.",
        "technique": "T1543.003",
    },
    "5": {
        "prompt": "Absolute path of the encryption staging directory. (Full path with backslashes.)",
        "hint": "`Get-WinEvent | include FileCreate` shows where the binary landed. `Get-ChildItem` confirms.",
        "technique": "T1074.001",
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
