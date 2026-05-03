# Memory Forensics

## Solution
1. Run `pslist` to see all processes - notice `svchost_update.exe` (PID 4892) running under explorer.exe instead of services.exe
2. Run `netscan` to see it connecting to suspicious IP `185.141.27.3`
3. Run `malfind` to confirm injected code in PID 4892
4. Run `strings 4892` to extract embedded strings - find a base64 string that decodes to the flag: `CTF{REDACTED}`
