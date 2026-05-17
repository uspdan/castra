"""Loopback validator for Tier 2: Privilege Escalation (tier-2-privilege-escalation).

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
        "prompt": "What is the full path of the unauthorised setuid binary\nthe attacker dropped on LNX-WEB-01? (Absolute path.)",
        "hint": "auditd SYSCALL type=PATH with mode=04... \u2014 chmod\n4755 against a binary outside the normal setuid set.",
        "answer": "REDACTED",
        "technique": "T1548.001"
    },
    "2": {
        "prompt": "What is the filename of the DLL injected into MsiExec.exe\non WIN-FIN-04? (Filename only, no path.)",
        "hint": "Sysmon EventID 7 (Image loaded) against `MsiExec.exe`\nfor an image outside `C:\\Windows\\System32`, immediately\nfollowed by EventID 8 with TargetImage=MsiExec.exe.",
        "answer": "REDACTED",
        "technique": "T1055.001"
    },
    "3": {
        "prompt": "Which non-System SID was the parent logon for the new\nREDACTED that suddenly held SeTcbPrivilege on WIN-FIN-09?\n(SID format S-1-5-21-...-XXXX.)",
        "hint": "REDACTED 4672 \u2014 SeTcbPrivilege granted to REDACTED; trace\nthe SubjectLogonId back to its 4624 row for the SID.",
        "answer": "REDACTED",
        "technique": "T1134.001"
    },
    "4": {
        "prompt": "Which dormant local account did the attacker reactivate\non LNX-WEB-02 to climb to root? (Username only.)",
        "hint": "auditd USER_CHAUTHTOK followed by a successful sshd\naccept for that user from 127.0.0.1.",
        "answer": "REDACTED",
        "technique": "T1078.003"
    },
    "5": {
        "prompt": "What was the exact registry value written under the\nms-settings shell-open hijack key on WIN-FIN-04? (The\nData field of the (Default) value, verbatim.)",
        "hint": "Sysmon EventID 13 (RegistryValueSet) \u2014 TargetObject ends\nwith `\\ms-settings\\shell\\open\\command\\(Default)`.",
        "answer": "C:\\Users\\REDACTED\\AppData\\Local\\Temp\\stage2.exe",
        "technique": "T1548.002"
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
