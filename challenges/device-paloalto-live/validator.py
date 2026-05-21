"""Loopback validator for the live PAN-OS GlobalProtect challenge."""

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
        "prompt": (
            "Which PAN-OS authentication-profile name has no "
            "multi-factor-auth block configured? (Exact name as it "
            "appears in the XML.)"
        ),
        "hint": (
            "`show config running | begin authentication-profile` and "
            "compare each entry — one is missing the "
            "`<multi-factor-auth>` element."
        ),
        "technique": "T1556.006",
    },
    "2": {
        "prompt": (
            "From which source IP did the GlobalProtect password "
            "spray originate? (Format x.x.x.x.)"
        ),
        "hint": (
            "`show log globalprotect | include auth-failure` — count "
            "by source-ip; one IP dominates."
        ),
        "technique": "T1110",
    },
    "3": {
        "prompt": (
            "Which VPN username eventually logged in successfully "
            "after the brute force? (Lowercase username only.)"
        ),
        "hint": (
            "`show log globalprotect | include auth-success` — same "
            "source IP as the failures."
        ),
        "technique": "T1078",
    },
    "4": {
        "prompt": (
            "What is the internal destination IP the attacker hit on "
            "TCP/3389 from the VPN tunnel? (Format x.x.x.x.)"
        ),
        "hint": (
            "`show log traffic | include ms-rdp` — source is the "
            "tunnel-ip (172.21.4.18), destination is the management "
            "subnet."
        ),
        "technique": "T1021.001",
    },
    "5": {
        "prompt": (
            "What is the name of the security rule that permitted "
            "the post-VPN pivot into the management subnet? (Exact "
            "rule name as it appears in the config and the traffic "
            "log.)"
        ),
        "hint": (
            "`show running security-policy` lists rules in evaluation "
            "order; cross-reference against the rule field in the "
            "RDP traffic log entries."
        ),
        "technique": "T1190",
    },
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
        if a is None:
            missing.append(qid)
        elif _normalise(a) != _normalise(q["answer"]):
            wrong.append(qid)
    if missing or wrong:
        return jsonify({"missing": missing, "wrong": wrong}), 400
    return jsonify({"flag": FLAG})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
