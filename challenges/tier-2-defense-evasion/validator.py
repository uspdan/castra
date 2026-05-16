"""Loopback validator for Tier 2: Defense Evasion (tier-2-defense-evasion).

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
        "prompt": "Which backdoor binary had its NTFS Modified timestamp\nrewritten to match the calc.exe creation date? (Full\npath or filename \u2014 answer with the filename only,\nincluding extension.)",
        "hint": "mft_audit.log lines tagged `timestamp_mismatch` \u2014\nModified < Created is the giveaway.",
        "answer": "REDACTED",
        "technique": "T1070.006"
    },
    "2": {
        "prompt": "Which Windows event channel did the attacker clear?\n(One word: System / REDACTED / Application / etc.)",
        "hint": "EID 1102 fires when an audit log is cleared and\nrecords the channel.",
        "answer": "REDACTED",
        "technique": "T1070.001"
    },
    "3": {
        "prompt": "What is the full path of the DLL that rundll32.exe\nloaded? (Full path as in sysmon.json.)",
        "hint": "Sysmon EID 1 process_creation; rundll32 invocations\nwith non-standard DLL paths are the focus.",
        "answer": "C:\\ProgramData\\Updates\\helper.dll",
        "technique": "T1218.011"
    },
    "4": {
        "prompt": "What packer signature did the file scanner identify on\nthe suspect binary? (Just the packer name, lowercase.)",
        "hint": "av_scan_report.log \u2014 each entry has a `packer_detected`\nfield. There's only one non-empty one.",
        "answer": "upx",
        "technique": "T1027.002"
    },
    "5": {
        "prompt": "What is the *display name* (Description field, including\ncasing) the attacker stamped onto their masquerading\nbinary's PE resources?",
        "hint": "pe_scan.log \u2014 compare the on-disk Description vs the\nsigner. The one with a Microsoft-sounding Description\nbut a non-Microsoft signer is the masquerade.",
        "answer": "REDACTED",
        "technique": "T1036.005"
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
