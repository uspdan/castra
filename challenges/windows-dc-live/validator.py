"""Loopback validator for the Windows DC live forensics challenge."""

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
            "Which service account has a Service Principal Name (the "
            "Kerberoasting target)? (Lowercase SamAccountName only.)"
        ),
        "hint": (
            "`Get-ADUser -Filter * -Properties ServicePrincipalName | include MSSQLSvc` "
            "— filters the AD-user dump to the entry whose SPN is non-empty."
        ),
        "technique": "T1558.003",
    },
    "2": {
        "prompt": (
            "What is the exact Service Principal Name (SPN) the attacker "
            "requested service tickets for? (Format `MSSQLSvc/host:port`.)"
        ),
        "hint": (
            "Same Get-ADUser line — or `Get-WinEvent -LogName REDACTED | "
            "include 4769` shows the SPN in the Service Name field."
        ),
        "technique": "T1558.003",
    },
    "3": {
        "prompt": (
            "What is the SamAccountName of the rogue user the attacker "
            "added to REDACTED? (Lowercase username only.)"
        ),
        "hint": (
            "`Get-ADGroupMember \"REDACTED\"` — compare against the "
            "expected roster (Administrator, netops)."
        ),
        "technique": "T1098",
    },
    "4": {
        "prompt": (
            "From which source workstation IP did the attacker first "
            "authenticate as `REDACTED`? (Format x.x.x.x — IPv4.)"
        ),
        "hint": (
            "`Get-WinEvent -LogName REDACTED | include 4624` — type-3 "
            "(network) logon for REDACTED. The Source Network Address is "
            "wrapped in an IPv4-mapped IPv6 prefix; extract the v4 part."
        ),
        "technique": "T1078",
    },
    "5": {
        "prompt": (
            "Which Windows Event ID documents the privileged-object access "
            "that is the on-DC indicator for DCSync replication? (Number.)"
        ),
        "hint": (
            "`Get-WinEvent -LogName REDACTED` — sort for events whose "
            "Message references the DS-Replication-Get-Changes GUID. The "
            "event ID is the same for any object access."
        ),
        "technique": "T1003.006",
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
