import jwt
import json
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)

SECRET_KEY = 's3cr3t_k3y_d0_n0t_l34k'
FLAG = 'CTF{REDACTED}'


@app.route('/')
def index():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JWT Forgery - API</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0a0a0a; color: #e0e0e0; min-height: 100vh; padding: 40px 20px; }
    .container { max-width: 800px; margin: 0 auto; }
    h1 { color: #00ff88; margin-bottom: 10px; font-size: 2em; }
    h2 { color: #ff6600; margin: 25px 0 10px; }
    .subtitle { color: #888; margin-bottom: 30px; }
    .endpoint { background: #1a1a2e; padding: 20px; border-radius: 10px; border: 1px solid #333; margin-bottom: 15px; }
    .method { display: inline-block; padding: 4px 10px; border-radius: 4px; font-weight: bold; margin-right: 10px; font-size: 14px; }
    .post { background: #004d00; color: #00ff88; }
    .get { background: #003366; color: #66b3ff; }
    .path { color: #fff; font-family: monospace; font-size: 16px; }
    .desc { color: #aaa; margin-top: 10px; }
    code { background: #0f0f1a; padding: 2px 6px; border-radius: 3px; color: #ff6600; font-size: 14px; }
    pre { background: #0f0f1a; padding: 15px; border-radius: 5px; overflow-x: auto; margin-top: 10px; color: #ccc; }
    .hint { background: #2a1a00; border: 1px solid #ff6600; padding: 15px; border-radius: 5px; margin-top: 20px; }
    .hint p { color: #ffaa44; }
  </style>
</head>
<body>
  <div class="container">
    <h1>JWT Forgery Challenge</h1>
    <p class="subtitle">A REST API secured with JSON Web Tokens. Can you forge your way to admin?</p>

    <h2>API Endpoints</h2>

    <div class="endpoint">
      <span class="method post">POST</span>
      <span class="path">/api/login</span>
      <p class="desc">Authenticate and receive a JWT token.</p>
      <pre>{
  "username": "guest",
  "password": "guest"
}</pre>
      <p class="desc" style="margin-top:10px;">Returns: <code>{"token": "eyJ..."}</code></p>
    </div>

    <div class="endpoint">
      <span class="method get">GET</span>
      <span class="path">/api/admin/flag</span>
      <p class="desc">Retrieve the flag. Requires admin role.</p>
      <p class="desc">Header: <code>Authorization: Bearer &lt;token&gt;</code></p>
    </div>

    <div class="hint">
      <p><strong>Objective:</strong> Login as guest, then find a way to escalate your privileges to admin to retrieve the flag.</p>
    </div>
  </div>
</body>
</html>'''


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    username = data.get('username', '')
    password = data.get('password', '')

    if username == 'guest' and password == 'guest':
        token = jwt.encode(
            {'sub': 'guest', 'role': 'user'},
            SECRET_KEY,
            algorithm='HS256'
        )
        return jsonify({'token': token})

    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/admin/flag', methods=['GET'])
def admin_flag():
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Authorization header with Bearer token required'}), 401

    token = auth_header.split(' ', 1)[1]

    try:
        # VULNERABILITY: When the algorithm header is "none", the token is
        # decoded without signature verification, allowing token forgery.
        header_segment = token.split('.')[0]
        # Add padding if needed
        padding = 4 - len(header_segment) % 4
        if padding != 4:
            header_segment += '=' * padding
        header = json.loads(base64.urlsafe_b64decode(header_segment))

        if header.get('alg', '').lower() == 'none':
            # Insecurely accept tokens with alg=none without verification
            payload_segment = token.split('.')[1]
            padding = 4 - len(payload_segment) % 4
            if padding != 4:
                payload_segment += '=' * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_segment))
        else:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except Exception as e:
        return jsonify({'error': f'Invalid token: {str(e)}'}), 401

    if payload.get('role') == 'admin':
        return jsonify({'flag': FLAG, 'message': 'Welcome, admin!'})

    return jsonify({'error': 'Access denied. Admin role required.', 'your_role': payload.get('role')}), 403


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
