"""Loopback validator for Device Forensics: GlobalProtect MFA Gap (device-paloalto-vpn).

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
        "prompt": "Which PAN-OS authentication profile name has no\nmulti-factor-auth block configured? (Exact name as it\nappears in the XML.)",
        "hint": "config.xml \u2014 under `<authentication-profile>` look for an\nentry where the `<multi-factor-auth>` element is absent.",
        "answer": "REDACTED",
        "technique": "T1556.006"
    },
    "2": {
        "prompt": "From which source IP did the GlobalProtect password spray\noriginate? (Format x.x.x.x.)",
        "hint": "globalprotect.log \u2014 count failed-login attempts by source\nIP. One IP has 200+ in a tight time window.",
        "answer": "REDACTED",
        "technique": "T1110"
    },
    "3": {
        "prompt": "Which VPN username eventually logged in successfully after\nthe brute force? (Lowercase username only, no domain.)",
        "hint": "globalprotect.log \u2014 same source IP as the previous\nquestion; status=auth-success.",
        "answer": "REDACTED",
        "technique": "T1078"
    },
    "4": {
        "prompt": "What is the internal destination IP the attacker hit on\nTCP/3389 from the VPN tunnel? (Format x.x.x.x.)",
        "hint": "traffic.log \u2014 look for `app=ms-rdp` from the\nGlobalProtect tunnel subnet (172.21.x.x) into the\nmanagement /24.",
        "answer": "REDACTED",
        "technique": "T1021.001"
    },
    "5": {
        "prompt": "What is the name of the security rule that permitted the\npost-VPN pivot into the management subnet? (Exact rule\nname as it appears in the XML and the traffic log.)",
        "hint": "Cross-reference traffic.log's `rule=` field with the\n`<entry name=\"...\">` in the rulebase section of\nconfig.xml.",
        "answer": "REDACTED",
        "technique": "T1190"
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
