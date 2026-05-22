"""Generate a weak 256-bit RSA key pair and encrypt the flag."""

import json
import os

# Two primes that multiply to a ~256-bit modulus — small enough that
# yafu / msieve / cado-nfs / fermat-factoring all crack the modulus in
# under a minute on a laptop. The previous values were composite, so
# phi(n) != (p-1)(q-1) and decryption never recovered the flag.
p = 338947817762649041627042079649009501639
q = 290245986740159562528702598831140273469

n = p * q  # ~256-bit modulus
phi = (p - 1) * (q - 1)
e = 65537


def modinv(a, m):
    """Extended Euclidean Algorithm to find modular inverse."""
    if a < 0:
        a = a % m
    g, x, _ = extended_gcd(a, m)
    if g != 1:
        raise ValueError("Modular inverse does not exist")
    return x % m


def extended_gcd(a, b):
    if a == 0:
        return b, 0, 1
    g, x, y = extended_gcd(b % a, a)
    return g, y - (b // a) * x, x


d = modinv(e, phi)

# Encrypt the flag (read from sealed sidecar staged into the image
# by scripts/stage-answers.sh — see CLAUDE.md §3.3).
with open("/opt/flag.txt") as _f:
    flag = _f.read().strip()
flag_int = int.from_bytes(flag.encode(), "big")
ciphertext = pow(flag_int, e, n)

keys = {
    "n": str(n),
    "e": e,
    "ciphertext": hex(ciphertext),
    "p": str(p),
    "q": str(q),
    "d": str(d),
}

os.makedirs("/data", exist_ok=True)
with open("/data/keys.json", "w") as f:
    json.dump(keys, f, indent=2)

print(f"n = {n}")
print(f"n bit length = {n.bit_length()}")
print(f"e = {e}")
print(f"ciphertext = {hex(ciphertext)}")
print("Keys saved to /data/keys.json")
