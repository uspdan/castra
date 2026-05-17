"""Loopback validator for Tier 2: Collection (tier-2-collection).

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
        "prompt": "What is the exact filename the attacker wrote the\nrecursive-findstr output to? (Filename only, no path.)",
        "hint": "Sysmon EventID 11 (FileCreate) for a `.txt` file written\nby `findstr.exe` or by its parent `REDACTED` immediately\nafter a findstr command.",
        "answer": "REDACTED",
        "technique": "T1005"
    },
    "2": {
        "prompt": "Which DLL is registered as the source of the\nWH_KEYBOARD_LL hook on FILE-01? (Filename only.)",
        "hint": "osquery `windows_hooks` table dump \u2014 `hook_type` column\nequals 13 (WH_KEYBOARD_LL).",
        "answer": "REDACTED",
        "technique": "T1056.001"
    },
    "3": {
        "prompt": "What file extension regex is the automated-collection\nloop filtering on? (As it appears in the PowerShell\ncommandline \u2014 e.g. `\\.(xls|csv)$`.)",
        "hint": "Sysmon EventID 1, Image=powershell.exe, parent=REDACTED,\ncommandline contains `-match` and a regex literal.",
        "answer": "\REDACTED",
        "technique": "T1119"
    },
    "4": {
        "prompt": "Which DLL backs the clipboard-polling hook? (Filename\nonly.)",
        "hint": "osquery `windows_hooks` again \u2014 different `hook_type`\nvalue (3 = WH_GETMESSAGE).",
        "answer": "REDACTED",
        "technique": "T1115"
    },
    "5": {
        "prompt": "What is the absolute path of the staging archive the\nattacker built before exfil? (Full path, including the\narchive filename.)",
        "hint": "Sysmon EventID 1 with `7z.exe` / `7za.exe` and a `-mhe=on`\nargument; the output path is the last positional arg.",
        "answer": "C:\\ProgramData\\Intel\\Logs\\stage.7z",
        "technique": "T1074.001"
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
