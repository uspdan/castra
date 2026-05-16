"""Loopback validator backend for threat-hunt-apt41.

Listens on 127.0.0.1:5000 inside the challenge container. The
``answer`` CLI (/usr/local/bin/answer) is the only intended client;
players can call it directly with curl if they really want to but
must do so from inside the container — the orchestrator only
publishes the SSH port.

Five questions, each one a free-text answer compared case-insensitively
against the canonical string. The flag is only revealed after all
five are correct.
"""

import json
import re
from flask import Flask, jsonify, request

app = Flask(__name__)

FLAG = "CTF{REDACTED}"

# Canonical answers. The exact strings are deliberately precise — they
# come straight out of the synthetic log corpus so a careful hunter
# extracts them verbatim. Matching is case-insensitive and tolerant of
# leading/trailing whitespace, but otherwise exact.
QUESTIONS = {
    "1": {
        "prompt": "Which web shell file did the attacker drop in the /uploads/ tree?",
        "answer": "REDACTED",
        "hint": "Look at IIS access.log POST requests landing on /uploads/ — only one of them targets a writable .aspx.",
    },
    "2": {
        "prompt": "What is the immediate parent process of the malicious REDACTED spawn?",
        "answer": "REDACTED",
        "hint": "Sysmon ProcessCreate events. The web shell runs *inside* the IIS worker process.",
    },
    "3": {
        "prompt": "What external domain did the attacker exfiltrate data to?",
        "answer": "REDACTED",
        "hint": "Pivot from the REDACTED → powershell.exe chain to a curl/Invoke-WebRequest call.",
    },
    "4": {
        "prompt": "What User-Agent string does the C2 beacon use?",
        "answer": "REDACTED",
        "hint": "Outbound proxy log — the same domain from question 3 shows up here with a distinctive UA.",
    },
    "5": {
        "prompt": "Which CVE did the attacker exploit for initial access?",
        "answer": "REDACTED",
        "hint": "The IIS access log shows the canonical ProxyLogon SSRF preceding the web shell drop.",
    },
}


def _normalise(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@app.route("/questions")
def questions():
    """List the questions a player still needs to answer."""
    return jsonify(
        {qid: {"prompt": q["prompt"], "hint": q["hint"]} for qid, q in QUESTIONS.items()}
    )


@app.route("/validate", methods=["POST"])
def validate():
    """Score one answer. Returns correctness + remaining hint."""
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
    """Reveal the flag iff every question's submitted answer is correct.

    The CLI is expected to POST a JSON map of ``{qid: answer}``.
    """
    data = request.get_json(force=True, silent=True) or {}
    answers = data.get("answers") or {}

    missing = []
    wrong = []
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
                "message": "Flag is revealed only when all five answers are correct.",
            }
        )

    return jsonify({"correct": True, "flag": FLAG})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
