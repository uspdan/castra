"""Generate a weak 256-bit RSA key pair and encrypt the flag."""

import json
import os

# Two primes that multiply to a ~256-bit modulus
# These are roughly 128-bit primes
p = 338947817762649041627042079649009501637
q = 290245986740159562528702598831140273467

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

# Encrypt the flag
flag = "CTF{REDACTED}"
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
