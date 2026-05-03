# dfir-001-memory-string artifacts

`process.dmp` is a 2 048-byte synthetic memory snippet generated with a
fixed random seed so the SHA-256 in `manifest.yaml` reproduces. The
flag is embedded as a NUL-terminated `FLAG=...` string roughly halfway
through the buffer; `strings -a` will surface it directly.

To regenerate (don't, unless you also update the manifest hash):

```python
import random
rng = random.Random(0x5ABBA7E)
random_bytes = bytes(rng.getrandbits(8) for _ in range(2048))
embedded = (
    b"\x00\x00ENV=\x00PWD=/home/analyst\x00USER=analyst"
    b"\x00FLAG=CTF{REDACTED}"
    b"\x00LANG=en_US.UTF-8\x00\x00"
)
open("process.dmp", "wb").write(random_bytes[:512] + embedded + random_bytes[512:])
```
