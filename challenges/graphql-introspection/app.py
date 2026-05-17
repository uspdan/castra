"""BlogQL — a tiny GraphQL API for blog posts.

The public site only ever uses the `posts` query. The schema also
declares a `secretAuditEntry` query that returns the flag — used
internally by an admin tool that always sets a debug header. The
field is documented as "internal — do not call from external
clients" and the frontend pretends it doesn't exist.

Introspection is enabled (default for graphene). Once the player
runs an __schema query they find every field, including the
secret one.

Player goal: pull the flag via GraphQL introspection.
"""

import json
import graphene
from flask import Flask, request, jsonify

app = Flask(__name__)

FLAG = "CTF{REDACTED}"

POSTS = [
    {"id": 1, "title": "Welcome to BlogQL", "body": "First post! Welcome.", "author": "team"},
    {"id": 2, "title": "On reliability",   "body": "Pillars: …",            "author": "team"},
    {"id": 3, "title": "Q2 roadmap",       "body": "Shipping more.",         "author": "team"},
]


class Post(graphene.ObjectType):
    id = graphene.Int()
    title = graphene.String()
    body = graphene.String()
    author = graphene.String()


class Query(graphene.ObjectType):
    posts = graphene.List(
        Post,
        description="Public list of blog posts.",
    )
    secret_audit_entry = graphene.String(
        description=(
            "Internal — do not call from external clients. "
            "Returns the current audit-key fingerprint for the admin dashboard."
        ),
    )

    def resolve_posts(self, info):
        return [Post(**p) for p in POSTS]

    def resolve_secret_audit_entry(self, info):
        # No auth check — the field is "secret" only by virtue of
        # not being documented externally. That is the bug.
        return FLAG


schema = graphene.Schema(query=Query)


GRAPHIQL = """<!doctype html>
<html><head><title>BlogQL</title><style>
body{font-family:system-ui;background:#0c0c18;color:#e8e8e8;padding:32px;max-width:820px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
.muted{color:#888}
</style></head><body>
<h1>BlogQL</h1>
<p class="muted">A tiny GraphQL API for blog posts.</p>

<div class="card">
  <strong>Endpoint</strong>
  <pre>POST /graphql
Content-Type: application/json

{"query": "{ posts { id title author } }"}</pre>
</div>

<div class="card">
  <strong>Public example response</strong>
  <pre>{
  "data": {
    "posts": [
      {"id": 1, "title": "Welcome to BlogQL", "author": "team"},
      ...
    ]
  }
}</pre>
</div>

<div class="card">
  <strong>Hint</strong>
  <p>The schema is queryable. A field you can <em>introspect</em>
  is a field you can <em>call</em>.</p>
</div>
</body></html>
"""


@app.route("/")
def home():
    return GRAPHIQL


@app.route("/graphql", methods=["POST"])
def graphql_endpoint():
    payload = request.get_json(silent=True) or {}
    query = payload.get("query")
    variables = payload.get("variables") or {}
    if not query:
        return jsonify({"error": "missing 'query' in JSON body"}), 400
    # graphene's default execute() enables introspection.
    result = schema.execute(query, variables=variables)
    out = {}
    if result.errors:
        out["errors"] = [str(e) for e in result.errors]
    if result.data is not None:
        out["data"] = result.data
    return jsonify(out)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
