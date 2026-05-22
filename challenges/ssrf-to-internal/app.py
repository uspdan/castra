import requests
from flask import Flask, request, jsonify
from urllib.parse import urlparse

app = Flask(__name__)

with open('/opt/flag.txt') as _f:
    FLAG = _f.read().strip()
BLOCKED_HOSTS = ['127.0.0.1', 'localhost', '0.0.0.0']


@app.route('/')
def index():
    return '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SSRF to Internal - Image Preview</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0a0a0a; color: #e0e0e0; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 40px 20px; }
    h1 { color: #00ff88; margin-bottom: 10px; font-size: 2em; }
    .subtitle { color: #888; margin-bottom: 30px; }
    .preview-box { background: #1a1a2e; padding: 30px; border-radius: 10px; border: 1px solid #333; width: 100%; max-width: 600px; margin-bottom: 20px; }
    .preview-box h2 { color: #00ff88; margin-bottom: 15px; }
    form { display: flex; flex-direction: column; gap: 15px; }
    input[type="text"] { padding: 12px; background: #0f0f1a; border: 1px solid #444; border-radius: 5px; color: #fff; font-size: 16px; }
    button { padding: 12px 24px; background: #00ff88; color: #000; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; font-size: 16px; }
    button:hover { background: #00cc6a; }
    .result { background: #1a1a2e; padding: 20px; border-radius: 10px; border: 1px solid #333; width: 100%; max-width: 600px; margin-top: 15px; }
    .result pre { white-space: pre-wrap; word-break: break-all; color: #ccc; }
    .info { background: #001a33; border: 1px solid #0066cc; padding: 15px; border-radius: 5px; margin-top: 20px; width: 100%; max-width: 600px; }
    .info p { color: #66b3ff; }
    #preview-result { margin-top: 15px; }
    .error { color: #ff4444; }
    .success { color: #00ff88; }
  </style>
</head>
<body>
  <h1>Image Preview Service</h1>
  <p class="subtitle">Enter a URL to preview its contents server-side</p>

  <div class="preview-box">
    <h2>Fetch URL</h2>
    <form id="preview-form">
      <input type="text" id="url-input" name="url" placeholder="https://example.com/image.png">
      <button type="submit">Preview</button>
    </form>
    <div id="preview-result"></div>
  </div>

  <div class="info">
    <p><strong>Note:</strong> For security, requests to 127.0.0.1 and localhost are blocked.</p>
  </div>

  <script>
    document.getElementById('preview-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const url = document.getElementById('url-input').value;
      const result = document.getElementById('preview-result');
      result.innerHTML = '<p>Fetching...</p>';
      try {
        const resp = await fetch('/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url })
        });
        const data = await resp.json();
        if (data.error) {
          result.innerHTML = '<p class="error">' + data.error + '</p>';
        } else {
          result.innerHTML = '<div class="result"><pre>' + (data.content || '') + '</pre></div>';
        }
      } catch (err) {
        result.innerHTML = '<p class="error">Error: ' + err.message + '</p>';
      }
    });
  </script>
</body>
</html>'''


@app.route('/preview', methods=['POST'])
def preview():
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({'error': 'Please provide a URL'}), 400

    url = data['url']

    # Basic security filter - blocks common loopback addresses
    parsed = urlparse(url)
    hostname = parsed.hostname or ''

    for blocked in BLOCKED_HOSTS:
        if blocked in hostname.lower():
            return jsonify({'error': f'Access to {hostname} is blocked for security reasons'}), 403

    try:
        resp = requests.get(url, timeout=5)
        content = resp.text[:10000]
        return jsonify({'content': content, 'status_code': resp.status_code})
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Could not connect to the provided URL'}), 400
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timed out'}), 400
    except Exception as e:
        return jsonify({'error': f'Error fetching URL: {str(e)}'}), 400


# Internal cloud metadata endpoint (simulated)
# In a real cloud environment this would be the metadata service at 169.254.169.254
# Here we serve it on the same Flask app but only respond to the metadata path
@app.route('/latest/meta-data/iam/credentials', methods=['GET'])
def metadata_credentials():
    return jsonify({
        'Code': 'Success',
        'Type': 'AWS',
        'AccessKey': FLAG,
        'SecretAccessKey': 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
        'Token': 'FwoGZXIvYXdzEBYaDHqa0AP1LGMEz...',
        'Expiration': '2099-12-31T23:59:59Z'
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
