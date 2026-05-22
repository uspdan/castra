"""Flask app providing log search UI and validation endpoint."""

import json
from flask import Flask, request, jsonify

app = Flask(__name__)

with open("/data/logs.txt") as f:
    LOG_LINES = f.read().splitlines()

with open('/opt/flag.txt') as _f:
    FLAG = _f.read().strip()
CORRECT_IP = "10.0.0.47"
CORRECT_USER = "admin"
CORRECT_TIMESTAMP = "2024-03-15T14:23:47Z"


@app.route("/")
def index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Splunk Threat Hunt</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Courier New', monospace;
            background: #0a0e17;
            color: #c9d1d9;
            min-height: 100vh;
        }
        .header {
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 20px 40px;
        }
        .header h1 { color: #58a6ff; font-size: 1.4em; }
        .container {
            max-width: 1200px;
            margin: 20px auto;
            padding: 0 20px;
        }
        .instructions {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            color: #8b949e;
            line-height: 1.6;
        }
        .instructions strong { color: #f0883e; }
        .search-section {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .search-input {
            flex: 1;
            background: #0d1117;
            border: 1px solid #30363d;
            color: #c9d1d9;
            padding: 12px 16px;
            border-radius: 6px;
            font-family: 'Courier New', monospace;
            font-size: 1em;
        }
        .search-input:focus { outline: none; border-color: #58a6ff; }
        .btn {
            background: #238636;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.95em;
        }
        .btn:hover { background: #2ea043; }
        .btn-validate {
            background: #8957e5;
        }
        .btn-validate:hover { background: #a371f7; }
        .results-header {
            color: #8b949e;
            margin-bottom: 10px;
            font-size: 0.9em;
        }
        .results {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 15px;
            max-height: 400px;
            overflow-y: auto;
            font-size: 0.85em;
            line-height: 1.5;
        }
        .log-line { padding: 2px 0; }
        .log-line:hover { background: #161b22; }
        .highlight { color: #ffa657; }
        .validate-section {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }
        .validate-section h3 { color: #d2a8ff; margin-bottom: 15px; }
        .form-group {
            margin-bottom: 12px;
        }
        .form-group label {
            color: #8b949e;
            display: block;
            margin-bottom: 4px;
            font-size: 0.9em;
        }
        .form-input {
            background: #0d1117;
            border: 1px solid #30363d;
            color: #c9d1d9;
            padding: 8px 12px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            width: 300px;
        }
        .form-input:focus { outline: none; border-color: #58a6ff; }
        .result-msg {
            margin-top: 15px;
            padding: 12px;
            border-radius: 6px;
            font-weight: 600;
        }
        .result-msg.success {
            background: rgba(35, 134, 54, 0.2);
            border: 1px solid #238636;
            color: #7ee787;
        }
        .result-msg.error {
            background: rgba(218, 54, 51, 0.2);
            border: 1px solid #da3633;
            color: #ff7b72;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Splunk Threat Hunt - Log Analysis</h1>
    </div>
    <div class="container">
        <div class="instructions">
            <strong>Mission:</strong> Search through the security logs to identify a brute force attack.
            Find the attacker's IP address, the targeted username, and the exact timestamp of the
            successful login that followed the brute force attempt. Submit your findings below.
        </div>

        <div class="search-section">
            <input type="text" class="search-input" id="searchQuery"
                   placeholder="Search logs (e.g., 'Failed password', '10.0.0.47', 'admin')..."
                   onkeydown="if(event.key==='Enter')doSearch()">
            <button class="btn" onclick="doSearch()">Search</button>
        </div>

        <div class="results-header" id="resultsHeader"></div>
        <div class="results" id="results">
            <em style="color: #8b949e;">Enter a search query to search through the logs...</em>
        </div>

        <div class="validate-section">
            <h3>Submit Findings</h3>
            <div class="form-group">
                <label>Attacker IP Address:</label>
                <input type="text" class="form-input" id="attackerIp" placeholder="e.g., 10.0.0.x">
            </div>
            <div class="form-group">
                <label>Targeted Username:</label>
                <input type="text" class="form-input" id="targetUser" placeholder="e.g., admin">
            </div>
            <div class="form-group">
                <label>Successful Login Timestamp:</label>
                <input type="text" class="form-input" id="loginTimestamp" placeholder="e.g., 2024-03-15T14:23:47Z">
            </div>
            <button class="btn btn-validate" onclick="doValidate()">Validate Findings</button>
            <div id="validateResult"></div>
        </div>
    </div>

    <script>
        async function doSearch() {
            const q = document.getElementById('searchQuery').value.trim();
            if (!q) return;
            const res = await fetch('/search?q=' + encodeURIComponent(q));
            const data = await res.json();
            document.getElementById('resultsHeader').textContent =
                `Found ${data.count} matching log entries (showing first ${Math.min(data.count, 500)}):`;
            const container = document.getElementById('results');
            if (data.lines.length === 0) {
                container.innerHTML = '<em style="color:#8b949e;">No results found.</em>';
            } else {
                container.innerHTML = data.lines.map(line => {
                    const escaped = line.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                    const highlighted = escaped.replace(
                        new RegExp(q.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'), 'gi'),
                        match => '<span class="highlight">' + match + '</span>'
                    );
                    return '<div class="log-line">' + highlighted + '</div>';
                }).join('');
            }
        }

        async function doValidate() {
            const ip = document.getElementById('attackerIp').value.trim();
            const username = document.getElementById('targetUser').value.trim();
            const timestamp = document.getElementById('loginTimestamp').value.trim();
            const res = await fetch('/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ip, username, timestamp })
            });
            const data = await res.json();
            const el = document.getElementById('validateResult');
            if (data.correct) {
                el.innerHTML = '<div class="result-msg success">Correct! Flag: ' + data.flag + '</div>';
            } else {
                el.innerHTML = '<div class="result-msg error">Incorrect. ' + (data.message || 'Try again.') + '</div>';
            }
        }
    </script>
</body>
</html>"""


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"count": 0, "lines": []})

    matching = [line for line in LOG_LINES if q.lower() in line.lower()]
    return jsonify({
        "count": len(matching),
        "lines": matching[:500],
    })


@app.route("/validate", methods=["POST"])
def validate():
    data = request.get_json(force=True)
    ip = data.get("ip", "").strip()
    username = data.get("username", "").strip()
    timestamp = data.get("timestamp", "").strip()

    if ip == CORRECT_IP and username == CORRECT_USER and timestamp == CORRECT_TIMESTAMP:
        return jsonify({"correct": True, "flag": FLAG})

    hints = []
    if ip != CORRECT_IP:
        hints.append("IP address is incorrect.")
    if username != CORRECT_USER:
        hints.append("Username is incorrect.")
    if timestamp != CORRECT_TIMESTAMP:
        hints.append("Timestamp is incorrect.")

    return jsonify({"correct": False, "message": " ".join(hints)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
