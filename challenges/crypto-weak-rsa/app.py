"""Flask app that displays RSA public key and ciphertext."""

import json
from flask import Flask

app = Flask(__name__)

with open("/data/keys.json") as f:
    keys = json.load(f)

N = keys["n"]
E = keys["e"]
CIPHERTEXT = keys["ciphertext"]


@app.route("/")
def index():
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weak RSA Challenge</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Courier New', monospace;
            background: #0a0e17;
            color: #c9d1d9;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }}
        .container {{
            max-width: 800px;
            width: 100%;
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 40px;
        }}
        h1 {{
            color: #ff6b6b;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        .description {{
            color: #8b949e;
            margin-bottom: 30px;
            line-height: 1.6;
        }}
        .key-section {{
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .key-section h2 {{
            color: #58a6ff;
            margin-bottom: 15px;
            font-size: 1.2em;
        }}
        .key-label {{
            color: #f0883e;
            font-weight: bold;
            margin-top: 10px;
        }}
        .key-value {{
            color: #7ee787;
            word-break: break-all;
            margin: 5px 0 15px 0;
            padding: 10px;
            background: #0a0e17;
            border-radius: 4px;
            font-size: 0.9em;
            line-height: 1.4;
        }}
        .challenge-text {{
            color: #d2a8ff;
            font-style: italic;
            margin-top: 20px;
            padding: 15px;
            border-left: 3px solid #d2a8ff;
            background: rgba(210, 168, 255, 0.05);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Weak RSA Encryption Service</h1>
        <p class="description">
            We use state-of-the-art RSA encryption to protect our messages.
            Our encrypted communications are completely secure... right?
        </p>

        <div class="key-section">
            <h2>Public Key</h2>
            <div class="key-label">Modulus (n):</div>
            <div class="key-value">{N}</div>
            <div class="key-label">Public Exponent (e):</div>
            <div class="key-value">{E}</div>
        </div>

        <div class="key-section">
            <h2>Encrypted Message</h2>
            <div class="key-label">Ciphertext (hex):</div>
            <div class="key-value">{CIPHERTEXT}</div>
        </div>

        <div class="challenge-text">
            Decrypt the message to find the flag. The encrypted message contains
            a secret that proves you have broken the encryption.
        </div>
    </div>
</body>
</html>"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
