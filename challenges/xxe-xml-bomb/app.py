"""InvoiceLab — a B2B invoice ingestion endpoint.

Accepts an XML invoice over POST /invoices/import and returns a
parsed summary. The XML parser is the lxml libxml2 binding,
configured with external entity resolution explicitly ENABLED —
the historical default for many real services migrated from
Java/.NET stacks that expect SOAP-style DTDs.

Player goal: read /flag.txt via XXE.
"""

from flask import Flask, request
from lxml import etree

app = Flask(__name__)

PAGE = """<!doctype html>
<html><head><title>InvoiceLab</title><style>
body{font-family:system-ui;background:#0d0d18;color:#e4e4e4;padding:32px;max-width:760px;margin:auto}
h1{color:#7af}
.card{background:#15152a;padding:18px;border-radius:10px;border:1px solid #2c2c45;margin:18px 0}
pre{background:#000;padding:14px;border-radius:6px;color:#9fe;overflow-x:auto}
.muted{color:#888}
code{background:#000;padding:2px 5px;border-radius:3px;color:#fa6}
</style></head><body>
<h1>InvoiceLab</h1>
<p class="muted">B2B invoice ingestion — push XML, get summary JSON.</p>

<div class="card">
<strong>Endpoint</strong>
<pre>
POST /invoices/import
Content-Type: application/xml

&lt;invoice&gt;
  &lt;vendor&gt;Acme&lt;/vendor&gt;
  &lt;amount&gt;1499.00&lt;/amount&gt;
  &lt;note&gt;Q2 retainer&lt;/note&gt;
&lt;/invoice&gt;
</pre>
</div>

<div class="card">
<strong>Example response</strong>
<pre>{
  "vendor": "Acme",
  "amount": "1499.00",
  "note": "Q2 retainer"
}</pre>
</div>
</body></html>
"""


@app.route("/")
def home():
    return PAGE


@app.route("/invoices/import", methods=["POST"])
def invoices_import():
    body = request.get_data()
    if not body:
        return {"error": "empty body"}, 400
    # WHY: resolve_entities=True is the XXE sink — combined with
    # load_dtd=True the parser will fetch and expand external
    # entities from the doctype. Real services have shipped with
    # this exact misconfiguration for over a decade.
    parser = etree.XMLParser(
        resolve_entities=True,
        load_dtd=True,
        no_network=False,
    )
    try:
        root = etree.fromstring(body, parser=parser)
    except etree.XMLSyntaxError as exc:
        return {"error": "xml parse error", "detail": str(exc)}, 400

    def text_of(tag):
        el = root.find(tag)
        return el.text if el is not None else None

    return {
        "vendor": text_of("vendor"),
        "amount": text_of("amount"),
        "note": text_of("note"),
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
