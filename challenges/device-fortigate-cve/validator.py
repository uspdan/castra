"""Loopback validator for Device Forensics: FortiGate Auth Bypass (device-fortigate-cve).

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
        "prompt": "What value did the attacker put in the `Forwarded:` header's\n`for=` parameter to trigger the auth bypass? (Exact value\nas it appears after `for=` and before the next semicolon\nor end of header.)",
        "hint": "admin-https.log \u2014 requests with `Forwarded: for=...;\nby=...` immediately before the rogue admin appears. The\ncanonical CVE-2022-40684 trick uses a specific local-looking\nidentity here.",
        "answer": "REDACTED",
        "technique": "T1190"
    },
    "2": {
        "prompt": "What is the username of the rogue super_admin account\nadded during the bypass window? (Lowercase, as it appears\nin the config diff.)",
        "hint": "config-diff.txt \u2014 the `+config system admin / + edit ...`\nblock. The legitimate roster (in approved-admins.txt) does\nnot contain it.",
        "answer": "REDACTED",
        "technique": "T1078.003"
    },
    "3": {
        "prompt": "Which FortiOS admin profile setting did the attacker leave\nunrestricted on the rogue account so it would accept\nlogins from any source IP? (Exact CLI config keyword.)",
        "hint": "config-diff.txt for that account \u2014 look for the absence /\nwildcard of `REDACTED`.",
        "answer": "REDACTED",
        "technique": "T1556"
    },
    "4": {
        "prompt": "Which CIDR was added to the SSL-VPN portal's split-tunnel\nrouting-address list to expose the internal management\nsubnet? (Format x.x.x.x/yy.)",
        "hint": "config-diff.txt \u2014 within `config vpn ssl web portal / edit\nfull-access`, look for the new entry under\n`set split-tunneling-routing-address` or a referenced\nfirewall address group.",
        "answer": "REDACTED",
        "technique": "T1098"
    },
    "5": {
        "prompt": "What is the source IP from which the rogue admin\nsubsequently authenticated via the web GUI? (Format x.x.x.x.)",
        "hint": "system-event.log \u2014 `event=login` with `status=success`\nand the new username from the previous question.",
        "answer": "REDACTED",
        "technique": "T1078"
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
