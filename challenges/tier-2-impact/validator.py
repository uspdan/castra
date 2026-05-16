"""Loopback validator for Tier 2: Impact (tier-2-impact).

Factory-generated. The canonical answers are baked in below. Listens
on 127.0.0.1:5000 inside the challenge container — only reachable
from within (the orchestrator publishes only the SSH port).
"""

import re
from flask import Flask, jsonify, request

app = Flask(__name__)

FLAG = "CTF{REDACTED}"

QUESTIONS = {
    "1": {
        "prompt": "What file extension is appended to encrypted files on\nhost FILE-01? (Format: .ext, including the dot.)",
        "hint": "filesystem_changes.log \u2014 file creation events.",
        "answer": "REDACTED",
        "technique": "T1486"
    },
    "2": {
        "prompt": "Which Windows built-in did the attacker use to delete\nshadow copies on host BACKUP-2? (Filename, lowercase.)",
        "hint": "sysmon.json process_creation, command line includes\n`delete shadows`.",
        "answer": "REDACTED",
        "technique": "T1490"
    },
    "3": {
        "prompt": "What database directory on DB-3 was overwritten with\nrandom data? (Full path.)",
        "hint": "wipe_audit.log \u2014 look for the largest write of pattern\n`random` to a path under a database product folder.",
        "answer": "C:\\Program Files\\Microsoft SQL Server\\MSSQL16\\Data",
        "technique": "T1561.001"
    },
    "4": {
        "prompt": "How many files were deleted from FINANCE-9 in the bulk\ndelete operation? (Just the integer.)",
        "hint": "deletion_audit.log \u2014 single user/process responsible\nfor a count.",
        "answer": "187",
        "technique": "T1485"
    },
    "5": {
        "prompt": "How many admin accounts were disabled by the attacker\non AD-1? (Just the integer.)",
        "hint": "ad_changes.log \u2014 EID 4725 (account disabled) events\nwith the same actor.",
        "answer": "12",
        "technique": "T1531"
    }
}


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
