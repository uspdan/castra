"""Loopback validator for Tier 2: Exfiltration (tier-2-exfiltration).

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
        "prompt": "On host FINANCE-2 the C2 channel exfiltrated approximately\nhow many MB? (Integer, no units.)",
        "hint": "proxy.log \u2014 sum bytes_out for the host's beacon domain.\nSpike from the usual ~500-byte beacon size is the giveaway.",
        "technique": "T1041"
    },
    "2": {
        "prompt": "On host RND-7 which DNS record type is the attacker abusing\nfor the alternative exfiltration channel? (Upper-case\nthree-letter type, e.g. `TXT`.)",
        "hint": "dns_queries.log \u2014 RND-7's queries land on an unfamiliar\nSLD with a single record type repeated.",
        "technique": "T1048.003"
    },
    "3": {
        "prompt": "What is the AWS S3 bucket name the attacker uploaded to\nfrom host HR-3? (Just the bucket name, no s3:// prefix.)",
        "hint": "cli_history.log \u2014 search for aws s3 cp commands.",
        "technique": "T1567.002"
    },
    "4": {
        "prompt": "Between which two UTC hours does the attacker schedule\ntheir daily exfiltration on host LEGAL-1? Answer as\nHH:MM-HH:MM in 24-hour format.",
        "hint": "timeline.log on LEGAL-1 \u2014 the exfil transfers all\nshare an identical hour window.",
        "technique": "T1029"
    },
    "5": {
        "prompt": "On host MARKETING-2 the automated exfiltration script\nmonitors which folder for new files? (Full path as in\nwatcher.log.)",
        "hint": "watcher.log \u2014 line with `watch_path=\u2026` and `event=created`.",
        "technique": "T1020"
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
