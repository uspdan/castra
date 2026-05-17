"""Loopback validator for the pfSense live challenge."""

import re
from flask import Flask, jsonify, request

app = Flask(__name__)
FLAG = "CTF{REDACTED}"

QUESTIONS = {
    "1": {
        "prompt": "What is the username of the rogue admin account added via the WebGUI? (Lowercase username only.)",
        "hint": "`show users` — three users. Two belong; one was added with a `fullname` carrying a recent timestamp.",
        "answer": "REDACTED",
        "technique": "T1078",
    },
    "2": {
        "prompt": "From which source IP did the attacker successfully authenticate to the WebGUI? (Format x.x.x.x.)",
        "hint": "`show auth-log | include authenticated successfully` — same IP that previously had 200+ failures.",
        "answer": "REDACTED",
        "technique": "T1110",
    },
    "3": {
        "prompt": "What is the description (`descr`) of the rogue NAT rule? (Exact value as it appears in the config.)",
        "hint": "`show config | begin <nat>` shows the rule block — the `<descr>` field.",
        "answer": "REDACTED",
        "technique": "T1133",
    },
    "4": {
        "prompt": "What is the internal target IP the rogue NAT rule forwards to? (Format x.x.x.x.)",
        "hint": "`show nat` — the `rdr on em0 ... -> <IP> port 22` line.",
        "answer": "REDACTED",
        "technique": "T1021.004",
    },
    "5": {
        "prompt": "What WAN port does the rogue NAT rule listen on? (Port number only.)",
        "hint": "Same `show nat` line — the `port = <PORT>` before the `->`.",
        "answer": "REDACTED",
        "technique": "T1133",
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
