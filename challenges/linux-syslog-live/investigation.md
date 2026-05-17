# Investigation Briefing — lnx-web-02 (Live)

`lnx-web-02.corp.local` (Red Hat Enterprise Linux 9.3, Apache +
Tomcat) is a customer-facing web host. Network monitoring caught
an outbound TCP/4444 connection from this box thirty minutes ago.
Confirm.

## Connect

```sh
connect lnx-web-02
```

Any user/password lands you at a RHEL bash prompt.

## You have

A live RHEL bash session on `lnx-web-02` via `connect`.

## You need to answer

```
who
last
journalctl -u sshd
journalctl -u crond
cat /var/log/secure
cat /etc/passwd
ls /etc/cron.d
cat /etc/cron.d/<name>
cat /usr/local/bin/<name>.sh
find / -perm -4000 -type f
ps -ef
ss -tnp
ausearch -m USER_AUTH
```

Pipes (`| include`, `| match`, `| count`, etc.) work everywhere.

1. Source IPv4 of the successful SSH brute force.
2. Local username holding the resulting session.
3. SUID binary used for privilege escalation.
4. Filename under /etc/cron.d/ that landed the persistence.
5. Destination IPv4:port of the reverse-shell socket.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
