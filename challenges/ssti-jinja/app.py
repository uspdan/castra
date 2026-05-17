"""Greetly — a 'personalised greeting' page.

User-supplied name is concatenated into a Jinja2 template string
and passed to render_template_string. Classic SSTI: anything inside
{{ ... }} executes in the Jinja sandbox-less environment.

Player goal: SSTI -> RCE -> read /flag.txt.
"""

from flask import Flask, request, render_template_string

app = Flask(__name__)


HOME = """<!doctype html>
<html><head><title>Greetly</title><style>
body{font-family:system-ui;background:#0e0e1a;color:#eee;padding:32px;max-width:760px;margin:auto}
h1{color:#7af}
.card{background:#181830;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
input,button{font-family:inherit;padding:8px 12px;background:#0c0c18;color:#eee;border:1px solid #333;border-radius:6px}
button{background:#1e3a8a;border-color:#3b5bff;cursor:pointer}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
.muted{color:#888}
</style></head><body>
<h1>Greetly</h1>
<p class="muted">A truly personalised greeting service. Put your name in.</p>

<div class="card">
  <form method="GET" action="/greet">
    <label>Name: <input name="name" placeholder="Ada"/></label>
    <button>Greet me</button>
  </form>
</div>

<div class="card">
  <strong>Endpoint</strong>
  <pre>GET /greet?name=&lt;your name&gt;</pre>
</div>
</body></html>
"""


@app.route("/")
def home():
    return HOME


@app.route("/greet")
def greet():
    name = request.args.get("name", "world")
    # WHY: user-controlled string concatenated into a Jinja template
    # before rendering. SSTI sink by design.
    template = (
        "<!doctype html><html><body style='font-family:system-ui;"
        "background:#0e0e1a;color:#eee;padding:32px'>"
        f"<h2>Hello {name}!</h2>"
        "<p>Glad you stopped by.</p>"
        "<p><a href='/' style='color:#7af'>back</a></p>"
        "</body></html>"
    )
    return render_template_string(template)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
