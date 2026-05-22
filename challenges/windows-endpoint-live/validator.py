"""Loopback validator for the Windows endpoint live forensics challenge."""

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
        "prompt": "What is the filename of the macro-laden document the user opened? (Filename only, with extension.)",
        "hint": "`Get-WinEvent | include WINWORD` — the first EventID 1 in Sysmon shows WINWORD.EXE opening a file from Downloads.",
        "technique": "T1204.002",
    },
    "2": {
        "prompt": "What full URL does the decoded `-EncodedCommand` PowerShell pull its second stage from? (Full URL including scheme.)",
        "hint": "`Get-WinEvent | include EncodedCommand` — base64-decode the blob (the encoded text is UTF-8 base64 for this exercise, so `printf '<blob>' | base64 -d` works).",
        "technique": "T1059.001",
    },
    "3": {
        "prompt": "What is the name of the persistence scheduled task the attacker registered? (Exact TaskName.)",
        "hint": "`Get-ScheduledTask | include Intel` — one task name doesn't belong to a stock Windows / Intel image.",
        "technique": "T1053.005",
    },
    "4": {
        "prompt": "What is the C2 destination IP the persistence binary beacons to? (Format x.x.x.x.)",
        "hint": "`Get-NetTCPConnection | include Established` — the binary running as PID 8041 (update.exe) holds the C2 connection on port 443.",
        "technique": "T1071.001",
    },
    "5": {
        "prompt": "What is the absolute path of the binary the attacker drops to disk and persists via the scheduled task? (Full Windows path with backslashes.)",
        "hint": "`Get-WinEvent | include FileCreate` and `Get-ChildItem` (or `dir`) both reveal it under C:\\ProgramData\\Intel\\Logs\\.",
        "technique": "T1547",
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
