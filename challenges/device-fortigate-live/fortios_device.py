"""FortiOS 7.2.4 device data + grammar for FGT-PERIM-02.

FortiOS is single-mode for our forensics scope — no user/priv
hierarchy like Cisco; once authenticated you're at the
``FGT-PERIM-02 # `` prompt and the same shell handles all show /
get / execute / diagnose commands. (Real FortiOS has a ``config``
sub-tree for editing — we don't model that since forensics is
read-only.)

The shell-engine override hooks below adapt prompt + auth banner
to FortiOS conventions.
"""

from __future__ import annotations

import sys

HOSTNAME = "FGT-PERIM-02"

# FortiOS shows the model + serial banner before login. No "User
# Access Verification" string — banner is essentially the login
# banner you'd configure under `config system replacemsg admin`.
BANNER = """FortiGate-100F (FGT100FTK22000123)

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "{hostname} login: "
AUTH_PASSWORD_PROMPT = "Password: "

# Single-mode CLI — only USER. Suffix is ` # ` (FortiOS pads with
# spaces around #).
PROMPT_SUFFIXES = {"user": " # "}


# ---------------------------------------------------------------------------
# Canned outputs — mirror what a real `show full-configuration`,
# `get system status`, `execute log display` would produce on a
# post-incident FGT-PERIM-02.
# ---------------------------------------------------------------------------

GET_SYSTEM_STATUS = """Version: FortiGate-100F v7.2.4,build1396,230131 (GA)
REDACTED Level: 1
Serial-Number: FGT100FTK22000123
BIOS version: 05000000
System Part-Number: P22424-05
Log hard disk: Available
Hostname: FGT-PERIM-02
Operation Mode: NAT
Current virtual domain: root
Max number of virtual domains: 10
Virtual domains status: 1 in NAT mode, 0 in TP mode
Virtual domain configuration: disable
FIPS-CC mode: disable
Current HA mode: standalone
Branch point: 1396
Release Version Information: GA
FortiOS x86-64: Yes
System time: Fri May 15 06:55:11 2026
"""

SHOW_FULL_CONFIGURATION = """#config-version=FGT100F-7.2.4-FW-build1396-230131:opmode=0:vdom=0:user=REDACTED
config system global
    set hostname "FGT-PERIM-02"
    set timezone 24
end
config system admin
    edit "admin"
        set accprofile "super_admin"
        set REDACTED 10.10.0.0 255.255.255.0
        set vdom "root"
        set password ENC SHredacted
    next
    edit "noc-readonly"
        set accprofile "prof_noc_ro"
        set REDACTED 10.10.0.0 255.255.255.0
        set vdom "root"
        set password ENC SHredacted
    next
    edit "sso-fg-mgmt"
        set accprofile "super_admin"
        set remote-auth enable
        set remote-group "fg-break-glass"
        set vdom "root"
    next
    edit "REDACTED"
        set accprofile "super_admin"
        set vdom "root"
        set password ENC SH2redacted
    next
end
config firewall address
    edit "INTERNAL-MGMT"
        set subnet 10.250.0.0 255.255.255.0
    next
end
config vpn ssl web portal
    edit "full-access"
        set tunnel-mode enable
        set split-tunneling enable
        set split-tunneling-routing-address "INTERNAL-MGMT"
    next
end
"""

SHOW_SYSTEM_ADMIN = """config system admin
    edit "admin"
        set accprofile "super_admin"
        set REDACTED 10.10.0.0 255.255.255.0
        set vdom "root"
    next
    edit "noc-readonly"
        set accprofile "prof_noc_ro"
        set REDACTED 10.10.0.0 255.255.255.0
        set vdom "root"
    next
    edit "sso-fg-mgmt"
        set accprofile "super_admin"
        set remote-auth enable
        set remote-group "fg-break-glass"
        set vdom "root"
    next
    edit "REDACTED"
        set accprofile "super_admin"
        set vdom "root"
    next
end
"""

SHOW_VPN_SSL_PORTAL = """config vpn ssl web portal
    edit "full-access"
        set tunnel-mode enable
        set split-tunneling enable
        set split-tunneling-routing-address "INTERNAL-MGMT"
    next
    edit "web-only"
        set tunnel-mode disable
    next
end
"""

EXECUTE_LOG_DISPLAY = """1: date=2026-05-15 time=02:08:53 logid="0100032002" type="event" subtype="system" level="warning" logdesc="Admin login failed" action="login" status="failure" user="admin" srcip=REDACTED ui="https"
2: date=2026-05-15 time=02:09:01 logid="0100032003" type="event" subtype="system" level="notice"  logdesc="Object added"   action="add"   user="api" cfgobj="system.admin REDACTED"
3: date=2026-05-15 time=02:11:14 logid="0100032001" type="event" subtype="system" level="notice"  logdesc="Admin login successful" action="login" status="success" user="REDACTED" srcip=REDACTED ui="https" reason="passwd"
4: date=2026-05-15 time=02:14:22 logid="0100032004" type="event" subtype="system" level="notice"  logdesc="Object attribute changed" action="edit" user="REDACTED" cfgobj="vpn.ssl.web.portal full-access"
"""

ADMIN_HTTPS_LOG = """2026-05-15T02:08:51Z src=REDACTED method=GET  uri=/api/v2/cmdb/system/admin status=401 ua="python-requests/2.31.0"
2026-05-15T02:08:53Z src=REDACTED method=POST uri=/api/v2/cmdb/system/admin status=401 ua="python-requests/2.31.0"
2026-05-15T02:09:01Z src=REDACTED method=POST uri=/api/v2/cmdb/system/admin status=200 ua="Node.js" headers="Forwarded: for=REDACTED;by=REDACTED"
2026-05-15T02:09:02Z src=REDACTED method=PUT  uri=/api/v2/cmdb/system/admin/REDACTED status=200 ua="Node.js" headers="Forwarded: for=REDACTED;by=REDACTED"
2026-05-15T02:11:14Z src=REDACTED method=POST uri=/logincheck status=302 ua="Mozilla/5.0"
2026-05-15T02:14:22Z src=REDACTED method=POST uri=/api/v2/cmdb/vpn.ssl.web/portal/full-access status=200 ua="Mozilla/5.0"
"""

DIAG_DEBUG = "Debug application enabled. (no output for this challenge.)\n"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _get_system_status(shell, args):
    return GET_SYSTEM_STATUS


def _show_full_config(shell, args):
    return SHOW_FULL_CONFIGURATION


def _show_system_admin(shell, args):
    return SHOW_SYSTEM_ADMIN


def _show_vpn_ssl_portal(shell, args):
    return SHOW_VPN_SSL_PORTAL


def _execute_log_display(shell, args):
    return EXECUTE_LOG_DISPLAY


def _diag_debug(shell, args):
    return DIAG_DEBUG


def _execute_log_filter(shell, args):
    return ""  # silent — match real FortiOS


def _show_admin_https_log(shell, args):
    # FortiOS doesn't expose this on the CLI; we surface it as a
    # synthetic `show admin-https-log` command for the challenge —
    # in a real IR the file would arrive via `execute backup logs`.
    return ADMIN_HTTPS_LOG


def _exit(shell, args):
    sys.stdout.write("\n")
    raise SystemExit


def _noop(shell, args):
    return ""


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

GRAMMAR = {
    "get": {
        "system": {"status": {"fn": _get_system_status}},
    },
    "show": {
        "full-configuration": {"fn": _show_full_config},
        "system": {"admin": {"fn": _show_system_admin}},
        "vpn": {"ssl": {"web": {"portal": {"fn": _show_vpn_ssl_portal}}}},
        # synthetic — IR-style log dump exposed as a show command
        "admin-https-log": {"fn": _show_admin_https_log},
    },
    "execute": {
        "log": {
            "display": {"fn": _execute_log_display},
            "filter": {"fn": _execute_log_filter},
        },
    },
    "diagnose": {
        "debug": {"fn": _diag_debug},
    },
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
    "logout": {"fn": _exit},
}
