"""Loopback validator for Device Forensics: Cisco IOS Compromise (device-cisco-ios).

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
        "prompt": "What is the username of the rogue privilege-level-15 local\naccount the attacker added? (Lowercase username only.)",
        "hint": "running-config.txt \u2014 look for `username ... privilege 15`\nentries and compare to /home/hunter/logs/approved-users.txt.",
        "answer": "REDACTED",
        "technique": "T1078"
    },
    "2": {
        "prompt": "What is the SNMP community string configured with RW\n(read-write) access? (Exact string, case-sensitive.)",
        "hint": "running-config.txt and show-snmp.txt both name it. Look\nfor `snmp-server community ... RW`.",
        "answer": "REDACTED",
        "technique": "T1078.001"
    },
    "3": {
        "prompt": "What is the destination IP of the unauthorised GRE tunnel\nthe attacker created on Tunnel0? (Format x.x.x.x.)",
        "hint": "running-config.txt \u2014 `interface Tunnel0` block, look at\n`tunnel destination`.",
        "answer": "REDACTED",
        "technique": "T1133"
    },
    "4": {
        "prompt": "Which ACL number was modified to permit outbound traffic\nto the attacker's C2 prefix? (Number only, e.g. 103.)",
        "hint": "running-config.txt \u2014 look for `access-list NNN permit ...\n198.51.100.0 0.0.0.255` (the C2 /24 the GRE points into).",
        "answer": "102",
        "technique": "T1562.004"
    },
    "5": {
        "prompt": "From which source IP did the attacker authenticate to the\nvty over SSH for the privileged config changes? (Format\nx.x.x.x.)",
        "hint": "syslog.txt \u2014 multiple `%SEC_LOGIN-5-LOGIN_SUCCESS` lines\nfrom the same external IP into vty 0; show-users.txt\nconfirms the live session.",
        "answer": "REDACTED",
        "technique": "T1021.004"
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
