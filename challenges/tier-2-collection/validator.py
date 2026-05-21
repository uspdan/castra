"""Loopback validator for Tier 2: Collection (tier-2-collection).

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
        "prompt": "What is the exact filename the attacker wrote the\nrecursive-findstr output to? (Filename only, no path.)",
        "hint": "Sysmon EventID 11 (FileCreate) for a `.txt` file written\nby `findstr.exe` or by its parent `REDACTED` immediately\nafter a findstr command.",
        "technique": "T1005"
    },
    "2": {
        "prompt": "Which DLL is registered as the source of the\nWH_KEYBOARD_LL hook on FILE-01? (Filename only.)",
        "hint": "osquery `windows_hooks` table dump \u2014 `hook_type` column\nequals 13 (WH_KEYBOARD_LL).",
        "technique": "T1056.001"
    },
    "3": {
        "prompt": "What file extension regex is the automated-collection\nloop filtering on? (As it appears in the PowerShell\ncommandline \u2014 e.g. `\\.(xls|csv)$`.)",
        "hint": "Sysmon EventID 1, Image=powershell.exe, parent=REDACTED,\ncommandline contains `-match` and a regex literal.",
        "technique": "T1119"
    },
    "4": {
        "prompt": "Which DLL backs the clipboard-polling hook? (Filename\nonly.)",
        "hint": "osquery `windows_hooks` again \u2014 different `hook_type`\nvalue (3 = WH_GETMESSAGE).",
        "technique": "T1115"
    },
    "5": {
        "prompt": "What is the absolute path of the staging archive the\nattacker built before exfil? (Full path, including the\narchive filename.)",
        "hint": "Sysmon EventID 1 with `7z.exe` / `7za.exe` and a `-mhe=on`\nargument; the output path is the last positional arg.",
        "technique": "T1074.001"
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
