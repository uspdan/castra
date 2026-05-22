"""Loopback validator for Tier 2: Lateral Movement (tier-2-lateral-movement).

Factory-generated. The canonical answers are baked in below. Listens
on 127.0.0.1:5000 inside the challenge container — only reachable
from within (the orchestrator publishes only the SSH port).
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
        "prompt": "Which protocol did the attacker use to move from WORK01 to FILE01?\n(One word, lowercase.)",
        "hint": "security.log on FILE01 \u2014 look for EID 4624 with LogonType=10.",
        "technique": "T1021.001"
    },
    "2": {
        "prompt": "What hidden SMB share name did the attacker access on DC01?\n(Format: <share name>, e.g. `C$`.)",
        "hint": "smb_session.log on DC01 \u2014 look for an unusual access from\nFILE01's machine account.",
        "technique": "T1021.002"
    },
    "3": {
        "prompt": "Which Microsoft binary (lowercase, full filename) did the\nattacker invoke locally to spawn the remote process on DC02?",
        "hint": "Sysmon on the calling host shows the binary in\n`CommandLine`. Think classic WMI dual-use tool.",
        "technique": "T1047"
    },
    "4": {
        "prompt": "What is the name of the scheduled task the attacker created\non AUDIT01? (Exact string, as logged.)",
        "hint": "Sysmon EID 1 / schtasks.exe with the /tn argument.",
        "technique": "T1053.005"
    },
    "5": {
        "prompt": "What DCOM ProgID did the attacker abuse for the final hop?\n(Lowercase, including the dot.)",
        "hint": "Sysmon shows the powershell.exe call invoking\n`[Activator]::CreateInstance(...)` on a specific ProgID.",
        "technique": "T1021.003"
    }
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
