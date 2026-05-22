"""TokenStop — issues RS256 tokens, verifies them with a tiny
hand-rolled JWT validator that accepts both HS256 and RS256.

The vulnerability is the textbook JWT algorithm-confusion bug:
when the token header says alg=HS256, the validator uses the
PEM-encoded public key as the HMAC secret. The public key is —
by design — public. /public-key serves it. The attacker fetches
the PEM, signs a token of their own with HS256 using the PEM
bytes as the secret, and the server accepts it.

Player goal: forge an admin token without ever seeing the private key.
"""

import base64
import hmac
import hashlib
import json

from flask import Flask, request, jsonify
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

app = Flask(__name__)

with open('/opt/flag.txt') as _f:
    FLAG = _f.read().strip()
# Generate an RS256 keypair once at startup.
_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_pub = _priv.public_key()
PRIV_PEM = _priv.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
PUB_PEM = _pub.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)


def b64url_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def jwt_sign_rs256(payload: dict) -> str:
    header = {"alg": "RS256", "typ": "JWT"}
    h = b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{h}.{p}".encode()
    sig = _priv.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{h}.{p}.{b64url_encode(sig)}"


def jwt_verify(token: str) -> dict:
    """Verify a JWT and return the decoded payload.

    Accepts both RS256 and HS256. When alg=HS256 the PUBLIC KEY PEM
    bytes are used as the HMAC secret — the vulnerable pattern.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("malformed jwt")
    h_b64, p_b64, sig_b64 = parts
    header = json.loads(b64url_decode(h_b64))
    payload = json.loads(b64url_decode(p_b64))
    sig = b64url_decode(sig_b64)
    signing_input = f"{h_b64}.{p_b64}".encode()

    alg = header.get("alg")
    if alg == "RS256":
        try:
            _pub.verify(sig, signing_input, padding.PKCS1v15(), hashes.SHA256())
        except Exception as exc:
            raise ValueError(f"bad RS256 signature: {exc}")
    elif alg == "HS256":
        # VULNERABLE: same "key" used regardless of algorithm. For
        # HS256 the PEM bytes themselves become the shared secret.
        expected = hmac.new(PUB_PEM, signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, sig):
            raise ValueError("bad HS256 signature")
    else:
        raise ValueError(f"alg {alg!r} not allowed")
    return payload


PAGE = """<!doctype html>
<html><head><title>TokenStop</title><style>
body{font-family:system-ui;background:#0c0c18;color:#e8e8e8;padding:32px;max-width:780px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
.muted{color:#888}
</style></head><body>
<h1>TokenStop</h1>
<p class="muted">JWT issuer + validator. Issues RS256, accepts whatever it gets handed.</p>

<div class="card">
<strong>Endpoints</strong>
<pre>
POST /login          { "username":"guest","password":"guest" } -> { "token": "eyJ..." }
GET  /public-key                                                 # the verifier's RS256 public key (PEM)
GET  /admin/flag                                                 Authorization: Bearer &lt;token-with-role-admin&gt;
</pre>
</div>

<div class="card">
<strong>Hint</strong>
<p>The verifier's source is right there in the container. Same key for both algorithms is rarely a good plan.</p>
</div>
</body></html>"""


@app.route("/")
def home():
    return PAGE


@app.route("/public-key")
def public_key():
    return PUB_PEM, 200, {"Content-Type": "application/x-pem-file"}


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    if data.get("username") == "guest" and data.get("password") == "guest":
        token = jwt_sign_rs256({"sub": "guest", "role": "user"})
        return jsonify({"token": token, "role": "user"})
    return jsonify({"error": "bad credentials"}), 401


@app.route("/admin/flag")
def admin_flag():
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        return jsonify({"error": "missing bearer token"}), 401
    token = h[7:]
    try:
        claims = jwt_verify(token)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 401
    if claims.get("role") != "admin":
        return jsonify({"error": "role is not admin", "claims": claims}), 403
    return jsonify({"flag": FLAG})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
