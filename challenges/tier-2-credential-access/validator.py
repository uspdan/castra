"""Loopback validator for Tier 2: Credential Access (tier-2-credential-access).

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
        "prompt": "What is the name of the .dmp file the attacker wrote\nwhen dumping LSASS? (Filename only.)",
        "hint": "Sysmon EID 11 FileCreate events with TargetFilename\nending in `.dmp`.",
        "answer": "REDACTED",
        "technique": "T1003.001"
    },
    "2": {
        "prompt": "What encryption type did the attacker request the TGS\nwith to enable offline cracking? (Format: rc4 or aes,\nfollowed by the bit size, e.g. `REDACTED` or `aes256`.)",
        "hint": "Domain Controller 4769 events show\nTicketEncryptionType. The weak/legacy choice is the\none to flag.",
        "answer": "REDACTED",
        "technique": "T1558.003"
    },
    "3": {
        "prompt": "Which compromised user account performed the DCSync\nreplication request against DC01? (UPN, e.g.\nuser@corp.local.)",
        "hint": "DC security log \u2014 EID REDACTED with object access including\nthe DS-Replication-Get-Changes-All right. The account\nwon't be a real domain admin.",
        "answer": "REDACTED",
        "technique": "T1003.006"
    },
    "4": {
        "prompt": "Which full file path did the attacker read out of the\nChrome user data directory? (As shown in sysmon.json.)",
        "hint": "Sysmon EID 1 \u2014 process_creation events with a child\nprocess touching `\\Google\\Chrome\\User Data\\Default\\`.",
        "answer": "C:\\Users\\jhoffman\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Login Data",
        "technique": "T1555.003"
    },
    "5": {
        "prompt": "What is the filename of the PFX file the attacker\naccessed? (Filename only, with extension.)",
        "hint": "Sysmon EID 11 FileCreate isn't enough \u2014 look for\nFileAccess (EID 12 / 13) events for .pfx extensions.",
        "answer": "REDACTED",
        "technique": "T1552.004"
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
