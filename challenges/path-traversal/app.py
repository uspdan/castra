"""DocsViewer — serves files from /var/www/docs/.

A "defensive" filter strips occurrences of "../" before joining
the file path to the docs root. The strip is a single replace
pass — it doesn't loop until stable, doesn't normalise, doesn't
canonicalise. Nested traversal sequences (`....//`) collapse back
to `../` after one pass and slip through.

Player goal: read /flag.txt.
"""

import os
from flask import Flask, request, abort

app = Flask(__name__)

DOCS_ROOT = "/var/www/docs"


def sanitize(path: str) -> str:
    """Strip ../ and ..\\ once. Looks careful. Isn't."""
    s = path.replace("../", "").replace("..\\", "")
    # Refuse anything that starts with / so callers can't pass
    # absolute paths. (Doesn't help against the bypass.)
    if s.startswith("/"):
        s = s.lstrip("/")
    return s


PAGE = """<!doctype html>
<html><head><title>DocsViewer</title><style>
body{font-family:system-ui;background:#0c0c18;color:#e8e8e8;padding:32px;max-width:780px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
.muted{color:#888}
</style></head><body>
<h1>DocsViewer</h1>
<p class="muted">Read project documentation from /var/www/docs/.</p>

<div class="card">
  <strong>Endpoint</strong>
  <pre>GET /view?file=&lt;filename&gt;</pre>
  <p>Defaults to <code>welcome.md</code> when no file is given.</p>
</div>

<div class="card">
  <strong>Examples</strong>
  <pre>
/view?file=welcome.md
/view?file=getting-started.md
/view?file=changelog.md
  </pre>
</div>

<div class="card">
  <strong>Hint</strong>
  <p>The filter strips <code>../</code> once. Recursion isn't its strong suit.</p>
</div>
</body></html>
"""


@app.route("/")
def home():
    return PAGE


@app.route("/view")
def view():
    name = request.args.get("file", "welcome.md")
    if len(name) > 200:
        abort(400, "file param too long")
    safe = sanitize(name)
    full = os.path.join(DOCS_ROOT, safe)
    try:
        # WHY: no os.path.realpath() containment check — the
        # sanitize() above is the only defence. After collapsing
        # nested sequences it returns a real "../" that joins out
        # of the docs root.
        with open(full, "rb") as f:
            body = f.read()
    except FileNotFoundError:
        abort(404, f"file not found: {safe}")
    except IsADirectoryError:
        abort(400, "is a directory")
    except PermissionError:
        abort(403, "permission denied")
    return body, 200, {"Content-Type": "text/plain; charset=utf-8"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
