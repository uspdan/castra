# Weak RSA Challenge

## Overview
A web service displays an RSA public key (n, e) and a ciphertext. The RSA key is intentionally weak (256-bit modulus) making it factorable.

## Solution

1. Visit the web page and note the modulus `n` and ciphertext
2. Factor `n` into its two prime factors `p` and `q` (use factordb.com, yafu, msieve, or even Python's sympy.factorint since it's only ~256 bits)
3. Compute `phi = (p - 1) * (q - 1)`
4. Compute the private exponent `d = inverse(e, phi)` where `e = 65537`
5. Decrypt: `plaintext = pow(ciphertext_int, d, n)`
6. Convert the resulting integer to bytes: `plaintext.to_bytes(length, 'big').decode()`
7. The decrypted message is the flag

## Example Python solve script
```python
from sympy import factorint

n = <modulus from page>
e = 65537
ct = <ciphertext from page as int>

factors = factorint(n)
p, q = list(factors.keys())
phi = (p - 1) * (q - 1)
d = pow(e, -1, phi)
pt = pow(ct, d, n)
print(pt.to_bytes((pt.bit_length() + 7) // 8, 'big').decode())
```

## Flag
`CTF{REDACTED}`
