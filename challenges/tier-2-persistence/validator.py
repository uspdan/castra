"""Loopback validator for Tier 2: Persistence (tier-2-persistence).

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
        "prompt": "What registry value name did the attacker create under the\nRun key? (Just the value name, exact case.)",
        "hint": "registry_audit.log \u2014 RegistryValueSet events with\nTargetObject ending in `\\Run\\<name>`.",
        "answer": "REDACTED",
        "technique": "T1547.001"
    },
    "2": {
        "prompt": "What is the exact name of the scheduled task the attacker\ncreated? (As shown in scheduled_tasks.log.)",
        "hint": "Filter to action=create.",
        "answer": "\\Microsoft\\Windows\\Defrag\\OptimiseCacheV2",
        "technique": "T1053.005"
    },
    "3": {
        "prompt": "What is the service name (not the display name) the\nattacker installed? (As shown in service_install.log.)",
        "hint": "Look for an install event with binPath pointing at a\nnon-standard location like C:\\ProgramData\\\u2026",
        "answer": "REDACTED",
        "technique": "T1543.003"
    },
    "4": {
        "prompt": "What is the name of the WMI EventConsumer the attacker\nregistered? (As stored in WMI repository.)",
        "hint": "wmi_subscriptions.log \u2014 look for the consumer record paired\nwith a __EventFilter and __FilterToConsumerBinding.",
        "answer": "REDACTED",
        "technique": "T1546.003"
    },
    "5": {
        "prompt": "What is the BITS job display name (DisplayName field)\nthe attacker created? (Exact string.)",
        "hint": "bits_jobs.log \u2014 focus on the entry whose RemoteName host\ndoesn't match any approved Microsoft / corp domain.",
        "answer": "REDACTED",
        "technique": "T1197"
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
