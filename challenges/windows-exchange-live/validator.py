"""Loopback validator for the Exchange ProxyShell live challenge."""

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
        "prompt": "What is the unauthenticated URL path the attacker hit to reach the Exchange backend via the AutoDiscover SSRF? (Exact path as it appears in the IIS log, no query string.)",
        "hint": "`Get-IISAccessLog | include autodiscover` — the path-traversal-via-autodiscover marker is in the cs-uri-stem field.",
        "technique": "T1190",
    },
    "2": {
        "prompt": "What is the filename of the .aspx webshell the attacker dropped under aspnet_client/system_web? (Filename only with extension.)",
        "hint": "`Get-ChildItem C:\\inetpub\\wwwroot\\aspnet_client\\system_web` — the lone .aspx file alongside two .pst exports.",
        "technique": "T1505.003",
    },
    "3": {
        "prompt": "Which mailbox alias was exported via the malicious New-MailboxExportRequest with the highest priority? (Mailbox alias only.)",
        "hint": "`Get-MailboxExportRequest` lists both jobs. The CFO mailbox is the higher-value target.",
        "technique": "T1114.002",
    },
    "4": {
        "prompt": "What is the FilePath the CFO mailbox was exported to? (Exact value from the export-request detail.)",
        "hint": "`Get-MailboxExportRequest -Identity MailboxExport-fb22` — the FilePath field.",
        "technique": "T1567",
    },
    "5": {
        "prompt": "From which source IP did the exploit traffic originate? (Format x.x.x.x.)",
        "hint": "`Get-IISAccessLog | include autodiscover` — the c-ip column.",
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
