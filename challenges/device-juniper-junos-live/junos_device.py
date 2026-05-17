"""Juniper SRX 340 / Junos 21.2 device data + grammar for
SRX-PERIM-01.

Junos has two modes the player will use:
* **operational** (``>``) — default. `show ... ` queries.
* **configure** (``#``) — entered via ``configure``. Edits and commits.

A bad-actor reused valid NOC credentials (``netops``) to push a
commit that adds a backdoor super-user account and widens a
security policy to permit traffic to the attacker's prefix.
"""

from __future__ import annotations

import sys

HOSTNAME = "srx-perim-01"

BANNER = """--- JUNOS 21.2R3-S2.5 Kernel 64-bit JNPR-12.1-20220110.7 ---

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "{hostname} (ttyu0)\n\nlogin: "
AUTH_PASSWORD_PROMPT = "Password: "

PROMPT_SUFFIXES = {"user": "> ", "config": "# "}


def PROMPT_FORMAT(host, mode, suffix):
    base = f"admin@{host}{suffix}"
    if mode == "config":
        return "[edit]\n" + base
    return base


SHOW_VERSION = """Hostname: srx-perim-01
Model: srx340
Junos: 21.2R3-S2.5
JUNOS Software Release [21.2R3-S2.5]
"""

SHOW_CONFIG_SET = """set system host-name srx-perim-01
set system login user netops uid 2000
set system login user netops class super-user
set system login user netops authentication encrypted-password "$6$NETOPSredacted"
set system login user monitor uid 2001
set system login user monitor class read-only
set system login user monitor authentication encrypted-password "$6$MONITORredacted"
set system login user REDACTED uid 2099
set system login user REDACTED class super-user
set system login user REDACTED authentication encrypted-password "$6$ROGUEredacted"
set system services ssh root-login deny
set interfaces ge-0/0/0 unit 0 family inet address 192.0.2.18/30
set interfaces ge-0/0/1 unit 0 family inet address 10.10.0.1/24
set security zones security-zone untrust interfaces ge-0/0/0.0
set security zones security-zone trust interfaces ge-0/0/1.0
set security policies from-zone trust to-zone untrust policy REDACTED match source-address mgmt-net
set security policies from-zone trust to-zone untrust policy REDACTED match destination-address any
set security policies from-zone trust to-zone untrust policy REDACTED match application junos-https
set security policies from-zone trust to-zone untrust policy REDACTED then permit
set security address-book global address mgmt-net 10.10.0.0/24
set security address-book global address attacker-c2 REDACTED
set security policies from-zone trust to-zone untrust policy REDACTED match destination-address attacker-c2
"""

SHOW_SYSTEM_LOGIN = """system {
    login {
        user netops { uid 2000; class super-user; }
        user monitor { uid 2001; class read-only; }
        user REDACTED { uid 2099; class super-user; }
    }
}
"""

SHOW_SYSTEM_USERS = """ 8:11AM  up 142 days, 4 hrs, 2 users, load averages: 0.12, 0.18, 0.22
USER     TTY      FROM                                            LOGIN@  IDLE WHAT
netops   pts/0    10.10.0.50                                      9:11AM  17:00 -cli (cli)
netops   pts/1    REDACTED                                    3:14AM  00:00 -cli (cli)
"""

SHOW_LOG_MESSAGES = """May 15 03:12:11 srx-perim-01 sshd[14411]: Accepted password for netops from REDACTED port 52144 ssh2
May 15 03:12:13 srx-perim-01 mgd[14422]: UI_CMDLINE_READ_LINE: User 'netops', command 'configure'
May 15 03:13:55 srx-perim-01 mgd[14422]: UI_CMDLINE_READ_LINE: User 'netops', command 'set system login user REDACTED class super-user'
May 15 03:14:11 srx-perim-01 mgd[14422]: UI_CMDLINE_READ_LINE: User 'netops', command 'set security address-book global address attacker-c2 REDACTED'
May 15 03:14:22 srx-perim-01 mgd[14422]: UI_COMMIT_PROGRESS: Commit operation in progress: commit complete
May 15 03:14:22 srx-perim-01 mgd[14422]: UI_COMMIT: User 'netops' requested 'commit' operation (sequence 7)
"""

SHOW_SYSTEM_COMMIT = """0   2026-05-15 03:14:22 UTC by netops via cli         (sequence 7)
    commit complete
1   2026-05-15 03:12:11 UTC by netops via cli         (sequence 6)
    commit complete
2   2026-05-14 11:08:01 UTC by netops via cli         (sequence 5)
    commit complete
3   2026-05-12 14:00:22 UTC by netops via cli         (sequence 4)
    commit complete
"""

SHOW_SECURITY_POLICIES = """From zone: trust, To zone: untrust
  Policy: REDACTED, State: enabled, Index: 4, Sequence number: 1
    Source addresses: mgmt-net
    Destination addresses: any, attacker-c2
    Applications: junos-https
    Action: permit
"""


def _show_version(s, a): return SHOW_VERSION
def _show_config_set(s, a): return SHOW_CONFIG_SET
def _show_system_login(s, a): return SHOW_SYSTEM_LOGIN
def _show_system_users(s, a): return SHOW_SYSTEM_USERS
def _show_log_messages(s, a): return SHOW_LOG_MESSAGES
def _show_system_commit(s, a): return SHOW_SYSTEM_COMMIT
def _show_security_policies(s, a): return SHOW_SECURITY_POLICIES


def _configure(s, a):
    s.mode = "config"
    return "Entering configuration mode\n"


def _commit(s, a):
    return "commit complete\n"


def _exit(s, a):
    if s.mode == "config":
        s.mode = "user"
        return "Exiting configuration mode\n"
    sys.stdout.write("\n"); raise SystemExit


def _noop(s, a):
    return ""


GRAMMAR = {
    "show": {
        "version": {"fn": _show_version},
        "configuration": {"fn": _show_config_set},  # treats trailing tokens as filter (ignored)
        "system": {
            "login": {"fn": _show_system_login},
            "users": {"fn": _show_system_users},
            "commit": {"fn": _show_system_commit},
        },
        "log": {"fn": _show_log_messages},  # `show log <anything>` => messages
        "security": {"policies": {"fn": _show_security_policies}},
    },
    "configure": {"fn": _configure},
    "commit": {"fn": _commit, "min_mode": "config"},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
    "logout": {"fn": _exit},
    "set": {"system": {"fn": _noop, "min_mode": "config"}},
    "request": {"system": {"commit": {"fn": _show_system_commit}}},
}
