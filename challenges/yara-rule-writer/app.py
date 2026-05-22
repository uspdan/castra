"""Flask app for YARA rule writing challenge."""

import json
import os
import tempfile
from flask import Flask, request, jsonify

app = Flask(__name__)

SAMPLES_DIR = "/samples"
with open('/opt/flag.txt') as _f:
    FLAG = _f.read().strip()
with open(os.path.join(SAMPLES_DIR, "manifest.json")) as f:
    MANIFEST = json.load(f)

SAMPLE_FILES = sorted([f for f in MANIFEST.keys()])
MALWARE_FILES = {f for f, label in MANIFEST.items() if label == "malware"}
BENIGN_FILES = {f for f, label in MANIFEST.items() if label == "benign"}


@app.route("/")
def index():
    file_list_html = ""
    for f in SAMPLE_FILES:
        size = os.path.getsize(os.path.join(SAMPLES_DIR, f))
        file_list_html += f'<tr><td>{f}</td><td>{size} bytes</td><td><a href="/download/{f}">Download</a></td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YARA Rule Writer Challenge</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Courier New', monospace;
            background: #0a0e17;
            color: #c9d1d9;
            min-height: 100vh;
        }}
        .header {{
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 20px 40px;
        }}
        .header h1 {{ color: #58a6ff; font-size: 1.4em; }}
        .container {{
            max-width: 1100px;
            margin: 20px auto;
            padding: 0 20px;
        }}
        .instructions {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            color: #8b949e;
            line-height: 1.6;
        }}
        .instructions strong {{ color: #f0883e; }}
        .two-col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .panel {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
        }}
        .panel h3 {{ color: #d2a8ff; margin-bottom: 15px; }}
        textarea {{
            width: 100%;
            height: 300px;
            background: #0d1117;
            border: 1px solid #30363d;
            color: #7ee787;
            padding: 15px;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            resize: vertical;
        }}
        textarea:focus {{ outline: none; border-color: #58a6ff; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.85em;
        }}
        th, td {{
            padding: 8px 12px;
            text-align: left;
            border-bottom: 1px solid #21262d;
        }}
        th {{ color: #8b949e; }}
        td a {{ color: #58a6ff; text-decoration: none; }}
        td a:hover {{ text-decoration: underline; }}
        .btn {{
            background: #238636;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            margin-top: 15px;
            font-size: 0.95em;
        }}
        .btn:hover {{ background: #2ea043; }}
        .results {{
            margin-top: 20px;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
        }}
        .results h3 {{ color: #d2a8ff; margin-bottom: 15px; }}
        .match {{ color: #da3633; }}
        .no-match {{ color: #7ee787; }}
        .result-row {{ padding: 4px 0; }}
        .flag-box {{
            background: rgba(35, 134, 54, 0.2);
            border: 1px solid #238636;
            color: #7ee787;
            padding: 15px;
            border-radius: 6px;
            margin-top: 15px;
            font-weight: 600;
            font-size: 1.1em;
        }}
        .error-box {{
            background: rgba(218, 54, 51, 0.2);
            border: 1px solid #da3633;
            color: #ff7b72;
            padding: 15px;
            border-radius: 6px;
            margin-top: 15px;
        }}
        .stats {{
            margin-top: 10px;
            color: #8b949e;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>YARA Rule Writer Challenge</h1>
    </div>
    <div class="container">
        <div class="instructions">
            <strong>Mission:</strong> Write a YARA rule that detects all 5 malware samples without any
            false positives on the 15 benign samples. You can download and analyze the samples to find
            unique indicators. Submit your YARA rule to scan all samples.
            <br><br>
            <strong>Hint:</strong> Malware samples contain specific strings like mutex names and user-agent
            strings that benign files do not have. Some benign files contain partial matches to make it tricky.
        </div>

        <div class="two-col">
            <div class="panel">
                <h3>YARA Rule</h3>
                <textarea id="yaraRule" placeholder='rule siege_malware {{
    strings:
        $mutex = "Global\\\\SiegeRangeC2Mutex"
    condition:
        $mutex
}}'></textarea>
                <button class="btn" onclick="scanSamples()">Scan Samples</button>
            </div>
            <div class="panel">
                <h3>Sample Files ({len(SAMPLE_FILES)} files)</h3>
                <table>
                    <thead><tr><th>Filename</th><th>Size</th><th></th></tr></thead>
                    <tbody>{file_list_html}</tbody>
                </table>
            </div>
        </div>

        <div class="results" id="results" style="display:none;"></div>
    </div>

    <script>
        async function scanSamples() {{
            const rule = document.getElementById('yaraRule').value;
            const res = await fetch('/scan', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ rule: rule }})
            }});
            const data = await res.json();
            const el = document.getElementById('results');
            el.style.display = 'block';

            if (data.error) {{
                el.innerHTML = '<h3>Results</h3><div class="error-box">' + data.error + '</div>';
                return;
            }}

            let html = '<h3>Scan Results</h3>';
            html += '<div class="stats">Matches: ' + data.matches + '/20 files</div>';

            if (data.flag) {{
                html += '<div class="flag-box">All malware detected with zero false positives! Flag: ' + data.flag + '</div>';
            }}

            html += '<table><thead><tr><th>File</th><th>Result</th></tr></thead><tbody>';
            for (const r of data.results) {{
                const cls = r.matched ? 'match' : 'no-match';
                const txt = r.matched ? 'DETECTED' : 'clean';
                html += '<tr><td>' + r.file + '</td><td class="' + cls + '">' + txt + '</td></tr>';
            }}
            html += '</tbody></table>';

            el.innerHTML = html;
        }}
    </script>
</body>
</html>"""


@app.route("/download/<filename>")
def download(filename):
    if filename not in MANIFEST:
        return "Not found", 404
    filepath = os.path.join(SAMPLES_DIR, filename)
    with open(filepath, "rb") as f:
        data = f.read()
    from flask import Response
    return Response(data, mimetype="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


@app.route("/scan", methods=["POST"])
def scan():
    try:
        import yara
    except ImportError:
        return jsonify({"error": "yara-python not installed on server"})

    data = request.get_json(force=True)
    rule_text = data.get("rule", "")

    if not rule_text.strip():
        return jsonify({"error": "Please provide a YARA rule."})

    # Compile the rule
    try:
        rule = yara.compile(source=rule_text)
    except yara.SyntaxError as e:
        return jsonify({"error": f"YARA syntax error: {str(e)}"})
    except Exception as e:
        return jsonify({"error": f"YARA compilation error: {str(e)}"})

    # Scan all samples
    results = []
    matched_malware = 0
    matched_benign = 0

    for filename in SAMPLE_FILES:
        filepath = os.path.join(SAMPLES_DIR, filename)
        matches = rule.match(filepath)
        is_matched = len(matches) > 0

        if is_matched and filename in MALWARE_FILES:
            matched_malware += 1
        elif is_matched and filename in BENIGN_FILES:
            matched_benign += 1

        results.append({
            "file": filename,
            "matched": is_matched,
        })

    total_matches = matched_malware + matched_benign
    flag = None

    if matched_malware == 5 and matched_benign == 0:
        flag = FLAG

    return jsonify({
        "results": results,
        "matches": total_matches,
        "malware_detected": matched_malware,
        "false_positives": matched_benign,
        "flag": flag,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
