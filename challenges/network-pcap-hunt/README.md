# Network PCAP Hunt - Solution

## Vulnerability

Credentials are transmitted in cleartext via an HTTP POST request within the captured network traffic.

## Steps to Solve

1. **Download the PCAP file** from the challenge page at `http://localhost/capture.pcap`.

2. **Open in Wireshark** or use command-line tools to analyze.

3. **Filter for HTTP POST requests**:
   - Wireshark filter: `http.request.method == "POST"`
   - tshark: `tshark -r capture.pcap -Y "http.request.method == POST" -T fields -e http.file_data`

4. **Examine the POST to /login**: Among the traffic, there is one HTTP POST request to `/login` containing form-encoded data:

   ```
   username=admin&password=CTF{REDACTED}
   ```

5. **Alternative approach** using strings:

   ```bash
   strings capture.pcap | grep "CTF{REDACTED}
```
