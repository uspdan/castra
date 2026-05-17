"""Loopback validator for Tier 2: Execution (tier-2-execution).

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
        "prompt": "What URL does the decoded PowerShell -EncodedCommand pull\nits second stage from? (Full URL, including scheme.)",
        "hint": "Sysmon EventID 1 with `Image=powershell.exe` and an\n`-EncodedCommand` argument. Base64-decode the blob in the\ncommandline.",
        "answer": "REDACTED",
        "technique": "T1059.001"
    },
    "2": {
        "prompt": "Which signed Windows binary does the REDACTED chain abuse\nto download the HTA? (Just the filename, e.g. foo.exe.)",
        "hint": "Look at the REDACTED /c argument string for a LOLBin used\nas an HTTP client.",
        "answer": "REDACTED",
        "technique": "T1059.003"
    },
    "3": {
        "prompt": "What is the exact task name the attacker registered with\nschtasks /create? (Case-sensitive, as it appears after /tn.)",
        "hint": "4698 \u2014 A scheduled task was created. The TaskName field is\nwhat you want.",
        "answer": "REDACTED",
        "technique": "T1053.005"
    },
    "4": {
        "prompt": "Which process injected a thread into lsass.exe via the\nNative API call? (Full image path as it appears in the\nSysmon SourceImage field.)",
        "hint": "Sysmon EventID 8, TargetImage ends with `lsass.exe` \u2014 the\nSourceImage is the loader.",
        "answer": "C:\\Users\\REDACTED\\AppData\\Local\\Temp\\svc-helper.exe",
        "technique": "T1106"
    },
    "5": {
        "prompt": "What filename did the user double-click to trigger the\nmacro execution? (Filename only, no path.)",
        "hint": "Sysmon EventID 1 with ParentImage ending in `WINWORD.EXE`\n\u2014 the OriginalFileName or CommandLine of the parent points\nat the document.",
        "answer": "REDACTED",
        "technique": "T1204.002"
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
