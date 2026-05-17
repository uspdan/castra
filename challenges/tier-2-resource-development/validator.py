"""Loopback validator for Tier 2: Resource Development (tier-2-resource-development).

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
        "prompt": "What is the homoglyph lookalike domain the adversary\nregistered? (Bare domain, exactly as it appears in WHOIS.)",
        "hint": "whois-export.json \u2014 find the entry where\n`homoglyph_of=example.com`.",
        "answer": "REDACTED",
        "technique": "T1583.001"
    },
    "2": {
        "prompt": "What is the handle (the LinkedIn username, the slug after\n`linkedin.com/in/`) of the impersonator-recruiter account?",
        "hint": "impersonation-report.json \u2014 `platform=linkedin`,\n`type=fabricated_persona`.",
        "answer": "REDACTED",
        "technique": "T1585.001"
    },
    "3": {
        "prompt": "What is the handle of the **compromised** (not fabricated)\nX/Twitter account the adversary now controls? (Without\nthe `@`.)",
        "hint": "impersonation-report.json \u2014 `platform=x` and\n`type=account_takeover` (not `fabricated_persona`).",
        "answer": "REDACTED",
        "technique": "T1586.001"
    },
    "4": {
        "prompt": "What is the SHA256 of the pre-staged tool the adversary\nuploaded? (64-char lowercase hex.)",
        "hint": "tool-intel-feed.json \u2014 the single entry with\n`confidence=high` and `cluster_match=true`.",
        "answer": "REDACTED",
        "technique": "T1588.002"
    },
    "5": {
        "prompt": "What is the FQDN that the adversary minted a Let's\nEncrypt certificate for, sitting on the lookalike domain?\n(Full hostname as it appears in the CT record.)",
        "hint": "ct-hits.json \u2014 find the issuer `Let's Encrypt` entry that\nchains to the lookalike domain from question 1.",
        "answer": "updates.REDACTED",
        "technique": "T1608.001"
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
