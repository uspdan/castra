"""Loopback validator for the MikroTik RouterOS live challenge."""

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
        "prompt": "What is the name of the unauthorised scheduled job (the one that wasn't there last week)? (Exact NAME column value.)",
        "hint": "`/system scheduler print` — the legit jobs are conf-bkp, ssh-keep-alive, tmp-cleanup. The fourth one isn't from your team.",
        "technique": "T1053",
    },
    "2": {
        "prompt": "Which local user is the owner of the malicious scheduler script? (Lowercase username only.)",
        "hint": "`/system script print` — the `owner=...` field on the script named after the scheduled job.",
        "technique": "T1078",
    },
    "3": {
        "prompt": "What is the C2 domain the script's `/tool fetch` calls out to? (Bare FQDN, no scheme.)",
        "hint": "`/system script print` — `/tool fetch url=http://<DOMAIN>/...`.",
        "technique": "T1071.001",
    },
    "4": {
        "prompt": "What is the comment (the `;;;` annotation) on the rogue NAT rule that exposes an internal host? (Exact comment text — no quotes, no semicolons.)",
        "hint": "`/ip firewall nat print` — three rules. The one with chain=dstnat and in-interface=ether1 that maps to a high port.",
        "technique": "T1133",
    },
    "5": {
        "prompt": "What internal IP does that NAT rule forward to on TCP/22? (Format x.x.x.x.)",
        "hint": "`/ip firewall nat print` — the `to-addresses=` field on the rogue rule.",
        "technique": "T1021.004",
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
