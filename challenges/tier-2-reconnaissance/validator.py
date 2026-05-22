"""Loopback validator for Tier 2: Reconnaissance (tier-2-reconnaissance).

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
        "prompt": "What is the source IP that drove the bulk\nvulnerability-template scan? (Format x.x.x.x.)",
        "hint": "waf.log \u2014 sort by ip count; the obvious outlier has a\nuser-agent containing the scanner name.",
        "technique": "T1595.002"
    },
    "2": {
        "prompt": "Which email-address format did the scraper infer from\nthe scrape? (Format string with `{first}` / `{last}`\nplaceholders \u2014 e.g. `REDACTED`.)",
        "hint": "linkedin-scrape-evidence.json \u2014 the `inferred_email_pattern`\nfield is right there.",
        "technique": "T1589.002"
    },
    "3": {
        "prompt": "Which exact server-version string from your edge fleet\nended up in the adversary's catalogue? (As it appears\nin the Server response header \u2014 verbatim.)",
        "hint": "waf.log \u2014 look at the `Server` header field for the\nrecords where the scanner IP probed `/` and the WAF\npassed them through.",
        "technique": "T1592"
    },
    "4": {
        "prompt": "Which city did the adversary's enrichment pass identify\nas the company's primary engineering office? (City name\nonly.)",
        "hint": "linkedin-scrape-evidence.json \u2014 the `primary_eng_site`\nblock has a city field.",
        "technique": "T1591.001"
    },
    "5": {
        "prompt": "Which corp hostname did the external scan-database\nreport flag as having an exposed admin panel? (Bare\nhostname, no scheme, as it appears in the asset report.)",
        "hint": "external-asset-report.json \u2014 the `flagged_assets` list\nhas one entry with `exposure=admin_panel`.",
        "technique": "T1596.005"
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
