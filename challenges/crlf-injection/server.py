"""RedirectorCo — a 'helpful' link-shortener with HTTP response
splitting.

The /redirect endpoint writes the response bytes directly to the
socket, splicing the user-supplied ?to= value into the Location
header without filtering CR or LF. A payload that embeds
\\r\\n\\r\\n breaks out of the first response and lets the
attacker smuggle a second one.

Player goal: cause the handler to emit a complete *second* HTTP
response inside the single connection — the server detects the
smuggled status line in its own output buffer and rewards you
with the flag appended to the bytes it sends back.
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote
import re

FLAG = b"CTF{REDACTED}"

INDEX = b"""<!doctype html>
<html><head><title>RedirectorCo</title><style>
body{font-family:system-ui;background:#0c0c18;color:#e8e8e8;padding:32px;max-width:760px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
.muted{color:#888}
</style></head><body>
<h1>RedirectorCo</h1>
<p class="muted">A tiny URL shortener. Give us a destination, we'll redirect.</p>

<div class="card">
  <strong>Endpoint</strong>
  <pre>GET /redirect?to=&lt;url&gt;</pre>
  <p class="muted">Responds with a 302 + Location: header.</p>
</div>

<div class="card">
  <strong>Examples</strong>
  <pre>
curl -i 'http://target:5000/redirect?to=https://example.com'
  </pre>
</div>

<div class="card">
  <strong>Hint</strong>
  <p>The handler writes the response straight to the socket — no
     header validation, no CR/LF filtering. Smuggle a complete
     second response (status line + headers + blank line) inside
     your <code>?to=</code> value and the server self-detects the
     split and dumps the flag at the tail.</p>
</div>
</body></html>
"""


SECOND_STATUS_LINE = re.compile(rb"\r\nHTTP/1\.[01]\s+\d{3}\s")


class Handler(BaseHTTPRequestHandler):
    # Keep server signature stable; turn off the noisy default logger.
    server_version = "RedirectorCo/1.0"

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self._send_body(200, b"text/html; charset=utf-8", INDEX)
            return

        if self.path.startswith("/redirect"):
            # Parse ?to= without any filtering. Deliberately weak.
            to = ""
            if "?" in self.path:
                _, qs = self.path.split("?", 1)
                for pair in qs.split("&"):
                    if pair.startswith("to="):
                        to = unquote(pair[3:])
                        break
            self._handle_redirect(to)
            return

        self._send_body(404, b"text/plain", b"not found\n")

    def _handle_redirect(self, to: str):
        body = b"<html><body>Redirecting...</body></html>"
        # VULNERABLE: raw socket write, no header validation. CR/LF
        # in `to` smuggles new headers and even a second response.
        out = (
            b"HTTP/1.1 302 Found\r\n"
            b"Server: RedirectorCo/1.0\r\n"
            b"Location: " + to.encode("latin-1", "replace") + b"\r\n"
            b"Content-Type: text/html; charset=utf-8\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n"
            b"Connection: close\r\n"
            b"\r\n" + body
        )
        # Self-detect: if our output buffer now contains a second
        # HTTP status line, the player has successfully smuggled a
        # response. Reward.
        if SECOND_STATUS_LINE.search(out):
            out += b"\r\n[ctf] smuggled response detected. flag: " + FLAG + b"\n"
        try:
            self.wfile.write(out)
        except Exception:
            pass

    def _send_body(self, status: int, ctype: bytes, body: bytes):
        try:
            self.send_response(status)
            self.send_header("Content-Type", ctype.decode())
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass


def main():
    httpd = ThreadingHTTPServer(("0.0.0.0", 5000), Handler)
    print("RedirectorCo on :5000")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
