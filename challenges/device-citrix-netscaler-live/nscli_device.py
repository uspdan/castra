"""Citrix ADC / NetScaler 13.1 grammar + canned outputs for
NS-PERIM-01.

Background: device hit by the CVE-2023-3519 family — unauthenticated
RCE via crafted POST against a Gateway / AAA virtual server. Public
reporting (Mandiant / TalosIntel) documents the attacker chain:
exploit → webshell drop under `/var/netscaler/logon/themes/` →
new system user → internal pivot. We model that.

The shell engine's per-device hooks adapt prompt + auth banner to
NetScaler nscli conventions.
"""

from __future__ import annotations

import sys

HOSTNAME = "NS-PERIM-01"

BANNER = """Last login: Wed May 14 18:23:11 2026 from 10.10.0.50 on console

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "login: "
AUTH_PASSWORD_PROMPT = "Password: "

# NetScaler nscli prompt — just `> `.
PROMPT_SUFFIXES = {"user": "> "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"{host}{suffix}"


# ---------------------------------------------------------------------------
# Canned outputs
# ---------------------------------------------------------------------------

SHOW_NS_VERSION = """  NetScaler NS13.1: Build 49.13.nc, Date: Mar 26 2024, 13:51:39   (64-bit)
"""

SHOW_NS_HARDWARE = """ Platform: NSMPX-15020 8*CPU+8*IX+2*E1K+4F+2*E1K-2P+8F 8002 1620
 Manufactured on: 4/12/2018
 CPU: 2700MHZ
 Host Id: 1714030252
 Serial no: ABC1234567
 Encoded serial no: ABC1234567
"""

SHOW_SYSTEM_USER = """1)  User Name: nsroot
        Allowed Management Interface: API CLI
        Logged in users: 1

2)  User Name: noc-readonly
        Allowed Management Interface: CLI
        Logged in users: 0

3)  User Name: REDACTED
        Allowed Management Interface: API CLI
        Logged in users: 0
        Command Policy: superuser

Done
"""

SHOW_VSERVER = """ 1) vs_gateway        SSL_VPN     192.0.2.18:443     UP     1     ACTIVE   100
 2) vs_aaa_idp        SSL         192.0.2.18:8443    UP     1     ACTIVE   100
 3) vs_lb_intranet    HTTP        10.10.0.81:80      UP     1     ACTIVE   100
 4) REDACTED TCP         10.10.0.91:22      UP     1     ACTIVE   100

Done
"""

SHOW_RUNNING_CONFIG = """# NS13.1 Build 49.13.nc
#
set ns config -IPAddress 10.10.0.1 -netmask 255.255.255.0
set ns hostname NS-PERIM-01
#
add system user nsroot e44eX...redacted
add system user noc-readonly aaaR...redacted -allowedManagementInterface CLI
add system user REDACTED cccQ...redacted -allowedManagementInterface API CLI
bind system user REDACTED superuser 100
#
add vpn vserver vs_gateway SSL 192.0.2.18 443
add ssl certKey ssl-cert -cert /nsconfig/ssl/wildcard.example.crt
#
add lb vserver vs_lb_intranet HTTP 10.10.0.81 80
add lb vserver REDACTED TCP 10.10.0.91 22 -timeout 7200
bind lb vserver REDACTED -servicename svc_dc_ssh
add server svc_dc_ssh_target REDACTED
add service svc_dc_ssh svc_dc_ssh_target TCP 22
#
add authentication policy auth_pol_noc -rule "ns_true" -action ldap_corp
add authentication policy auth_pol_unknown -rule "ns_true" -action local
"""

SHOW_HTTPACCESS_LOG = """2026-05-15T01:42:14Z REDACTED - - "GET /vpn/index.html HTTP/1.1" 200 4218 "-" "Mozilla/5.0"
2026-05-15T01:42:22Z REDACTED - - "POST REDACTED HTTP/1.1" 200 0    "-" "python-requests/2.31.0"
2026-05-15T01:42:24Z REDACTED - - "POST REDACTED HTTP/1.1" 200 412  "-" "python-requests/2.31.0"
2026-05-15T01:43:01Z REDACTED - - "GET /logon/themes/Default/REDACTED?cmd=id HTTP/1.1" 200 88   "-" "curl/8.4"
2026-05-15T01:43:09Z REDACTED - - "GET /logon/themes/Default/REDACTED?cmd=cat+/etc/passwd HTTP/1.1" 200 2418  "-" "curl/8.4"
2026-05-15T01:45:11Z REDACTED - - "GET /logon/themes/Default/REDACTED?cmd=nsapimgr_wr.sh+-+ HTTP/1.1" 200 412  "-" "curl/8.4"
"""

SHOW_NS_LOG = """May 15 01:42:24 NS-PERIM-01 AAA Message 1 0 :  AAA-EXTRACT: extracted post-mfa response payload of length 8190 bytes (truncated)
May 15 01:42:25 NS-PERIM-01 PPE-0   :  GUI cmd: /var/netscaler/logon/themes/Default/REDACTED created (size=412)
May 15 01:43:09 NS-PERIM-01 PPE-0   :  shell command via webshell: cat /etc/passwd
May 15 01:44:32 NS-PERIM-01 cli     :  user nsroot ran: add system user REDACTED -allowedManagementInterface API CLI
May 15 01:44:55 NS-PERIM-01 cli     :  user nsroot ran: bind system user REDACTED superuser 100
May 15 01:45:11 NS-PERIM-01 cli     :  user REDACTED ran: add lb vserver REDACTED TCP 10.10.0.91 22
"""


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _show_ns_version(shell, args):
    return SHOW_NS_VERSION


def _show_ns_hardware(shell, args):
    return SHOW_NS_HARDWARE


def _show_system_user(shell, args):
    return SHOW_SYSTEM_USER


def _show_vserver(shell, args):
    return SHOW_VSERVER


def _show_running_config(shell, args):
    return SHOW_RUNNING_CONFIG


def _show_httpaccess(shell, args):
    return SHOW_HTTPACCESS_LOG


def _show_ns_log(shell, args):
    return SHOW_NS_LOG


def _exit(shell, args):
    sys.stdout.write("\nDone\n")
    raise SystemExit


def _shell(shell, args):
    return "% shell escape disabled for this exercise.\n"


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

GRAMMAR = {
    "show": {
        "ns": {
            "version": {"fn": _show_ns_version},
            "hardware": {"fn": _show_ns_hardware},
            "log": {"fn": _show_ns_log},  # synthetic — surface /var/log/ns.log
        },
        "system": {"user": {"fn": _show_system_user}},
        "vserver": {"fn": _show_vserver},
        "running": {"config": {"fn": _show_running_config}},
        # synthetic — surface httpaccess.log inline
        "httpaccess": {"fn": _show_httpaccess},
    },
    "shell": {"fn": _shell},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
    "logout": {"fn": _exit},
}
