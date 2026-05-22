"""Loopback validator for Tier 2: Initial Access (tier-2-initial-access).

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
        "prompt": "In office365_audit.log, which user opened the malicious\nattachment that triggered the macro chain? (Just the\nUPN, e.g. user@corp.local.)",
        "hint": "Filter for MailItemsAccessed + WordOrExcelMacroEnabled.",
        "technique": "T1566.001"
    },
    "2": {
        "prompt": "In webapp_access.log, which CVE was used to compromise\nthe public web server? (Format: CVE-YYYY-NNNNN.)",
        "hint": "Look for an LDAP-protocol JNDI string in a User-Agent or\nheader.",
        "technique": "T1190"
    },
    "3": {
        "prompt": "In sso_auth.log, what country code does the successful\nlogin come from that should have triggered an impossible-\ntravel alert? (Two-letter ISO code, uppercase.)",
        "hint": "Compare the successful logon with the user's other\nrecent successful logons in the same file.",
        "technique": "T1078"
    },
    "4": {
        "prompt": "In vpn_gateway.log, what is the attacker source IP that\nsuccessfully authenticated to the VPN after a port-scan\nburst? (Format: x.x.x.x.)",
        "hint": "The scan source and the successful logon share an IP.\nLook for repeated TCP RST on closed ports preceding the\naccepted login.",
        "technique": "T1133"
    },
    "5": {
        "prompt": "In supply_chain.log, what is the SHA256 of the package\nthat was distributed by the compromised update server?\n(Full hex string, lowercase.)",
        "hint": "The compromised update server is the *only* upstream that\nflipped its signing identity between consecutive\npublishes.",
        "technique": "T1195.002"
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
