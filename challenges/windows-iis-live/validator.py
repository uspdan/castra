"""Loopback validator for the IIS webshell live challenge."""

import re
from flask import Flask, jsonify, request

app = Flask(__name__)
FLAG = "CTF{REDACTED}"

QUESTIONS = {
    "1": {
        "prompt": "What is the full URI path of the .aspx webshell as it appears in the IIS access log? (Path only, no query string.)",
        "hint": "`Get-IISAccessLog | include aspx` — every webshell GET targets the same path under /uploads/avatars/.",
        "answer": "REDACTED",
        "technique": "T1505.003",
    },
    "2": {
        "prompt": "What is the source IP behind every webshell request? (Format x.x.x.x.)",
        "hint": "`Get-IISAccessLog | include aspx` — the c-ip column is identical across the requests.",
        "answer": "REDACTED",
        "technique": "T1190",
    },
    "3": {
        "prompt": "Which child process is spawned by REDACTED at the start of the webshell session? (Filename only, e.g. `foo.exe`.)",
        "hint": "`Get-WinEvent | include w3wp` — the CreatorProcessName field on the 4688 events.",
        "answer": "REDACTED",
        "technique": "T1059.003",
    },
    "4": {
        "prompt": "What is the absolute path of the second-stage binary the attacker downloaded? (Full Windows path. Environment variables expanded, with backslashes.)",
        "hint": "`Get-WinEvent | include nc.exe` — the NewProcessName of the final 4688 event resolves %TEMP% in context of the DefaultAppPool identity.",
        "answer": "C:\\Users\\DefaultAppPool\\AppData\\Local\\Temp\\nc.exe",
        "technique": "T1105",
    },
    "5": {
        "prompt": "What internal destination IP did the attacker pivot to over TCP/1433? (Format x.x.x.x.)",
        "hint": "`Get-NetTCPConnection | include Established` — the lone outbound connection on port 1433 from PID 8041.",
        "answer": "REDACTED",
        "technique": "T1021.002",
    },
}


def _normalise(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@app.route("/questions")
def questions():
    return jsonify({qid: {"prompt": q["prompt"], "hint": q["hint"]} for qid, q in QUESTIONS.items()})


@app.route("/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True, silent=True) or {}
    qid = str(data.get("question", "")).strip()
    q = QUESTIONS.get(qid)
    if q is None: return jsonify({"error": f"no such question: {qid!r}"}), 404
    return jsonify({"question": qid, "correct": _normalise(data.get("answer", "")) == _normalise(q["answer"])})


@app.route("/reveal", methods=["POST"])
def reveal():
    data = request.get_json(force=True, silent=True) or {}
    answers = data.get("answers") or {}
    missing, wrong = [], []
    for qid, q in QUESTIONS.items():
        a = answers.get(qid)
        if a is None: missing.append(qid)
        elif _normalise(a) != _normalise(q["answer"]): wrong.append(qid)
    if missing or wrong: return jsonify({"missing": missing, "wrong": wrong}), 400
    return jsonify({"flag": FLAG})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
