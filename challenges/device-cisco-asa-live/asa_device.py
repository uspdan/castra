"""Cisco ASA 9.16 device data + grammar for ASA-VPN-01.

Backdrop: a known-bad AnyConnect compromise pattern — the perimeter
ASA shipped with a contractor tunnel-group whose local-database
auth profile never had MFA wired in. An attacker hit the
WebVPN portal, brute-forced the contractor account, and pivoted.
"""

from __future__ import annotations

import sys

HOSTNAME = "ASA-VPN-01"

BANNER = """Trying 127.0.0.1...
Connected to asa-vpn-01.
Escape character is '^]'.

User Access Verification

"""

ENABLE_PASSWORD = "n0c-l3v3l-15"

PROMPT_SUFFIXES = {"user": ">", "privileged": "#", "config": "(config)#"}

RUNNING_CONFIG = """: Saved
: Hardware:   ASA5516, 8192 MB RAM, CPU Atom C2538 2400 MHz, 4 cores
:
ASA Version 9.16(3)19
!
hostname ASA-VPN-01
domain-name corp.example
enable password 8 ENABLEr3dacted
!
username netops password 8 NETOPSredacted privilege 15
username monitor password 8 MONITORredacted privilege 5
username REDACTED password 8 REDACTEDredacted privilege 1
!
interface GigabitEthernet1/1
 nameif outside
 security-level 0
 ip address 192.0.2.18 255.255.255.252
!
interface GigabitEthernet1/2
 nameif inside
 security-level 100
 ip address 10.10.0.1 255.255.255.0
!
webvpn
 enable outside
 anyconnect enable
!
group-policy gp_employees attributes
 vpn-tunnel-protocol ssl-client
 webvpn
  anyconnect mfa enable
!
group-policy gp_contractors attributes
 vpn-tunnel-protocol ssl-client
 webvpn
  anyconnect mfa disable
  ! NOTE: TempFix-2026-03-12, MFA reinstate pending (ticket NOC-3119)
!
tunnel-group EMPLOYEES type remote-access
tunnel-group EMPLOYEES general-attributes
 authentication-server-group LDAP-CORP
 default-group-policy gp_employees
!
tunnel-group REDACTED type remote-access
tunnel-group REDACTED general-attributes
 authentication-server-group REDACTED
 default-group-policy gp_contractors
!
"""

SHOW_VPN_SESSIONDB = """Username     : REDACTED       Index        : 12
Assigned IP  : 172.21.4.18            Public IP    : REDACTED
Protocol     : AnyConnect-Parent SSL-Tunnel
Encryption   : AnyConnect-Parent: (1)none  SSL-Tunnel: (1)AES-GCM-256
Group Policy : gp_contractors
Tunnel Group : REDACTED
Login Time   : 01:51:33 UTC Fri May 15 2026
Duration     : 0h:13m:42s
Inactivity   : 0h:00m:00s
NAC Result   : Unknown
VLAN Mapping : N/A                   VLAN: none

Username     : netops                 Index        : 7
Assigned IP  : 172.21.4.4             Public IP    : 10.10.0.50
Protocol     : AnyConnect-Parent SSL-Tunnel
Group Policy : gp_employees
Tunnel Group : EMPLOYEES
Login Time   : 09:11:01 UTC Thu May 14 2026
Duration     : 17h:51m:22s
"""

SHOW_LOGGING = """Syslog logging: enabled
Facility: 20
Timestamp logging: enabled
Standby logging: disabled
Trap logging: level informational

%ASA-6-722051: Group <REDACTED> User <REDACTED> IP <REDACTED> AAA login failure
%ASA-6-722051: Group <REDACTED> User <REDACTED> IP <REDACTED> AAA login failure
%ASA-6-722051: Group <REDACTED> User <REDACTED> IP <REDACTED> AAA login failure
... 234 more failures in 9 minutes ...
%ASA-6-113012: AAA user authentication Successful: local database: user = REDACTED
%ASA-6-722055: Group <REDACTED> User <REDACTED> IP <REDACTED> Reason: User reached maximum connection limit
%ASA-7-609001: Built local-host outside:REDACTED
%ASA-6-722022: Group <REDACTED> User <REDACTED> IP <REDACTED> TCP SVC connection established without compression
%ASA-6-302013: Built inbound TCP connection 14021 for outside:REDACTED/52144 (REDACTED/52144) to inside:REDACTED/3389 (172.21.4.18/52144) (REDACTED)
%ASA-6-302013: Built inbound TCP connection 14022 for outside:REDACTED/52145 (REDACTED/52145) to inside:REDACTED/3389 (172.21.4.18/52145) (REDACTED)
"""

SHOW_TUNNEL_GROUP_INFO = """Tunnel-group EMPLOYEES, type Remote-Access
  Authentication Server Group LDAP-CORP
  Default Group Policy: gp_employees

Tunnel-group REDACTED, type Remote-Access
  Authentication Server Group REDACTED
  Default Group Policy: gp_contractors
"""

SHOW_WEBVPN_STATS = """WebVPN AnyConnect statistics:
  Active SSL VPN sessions: 2
  Active AnyConnect connections: 2
  Total cumulative connections: 14821
  Peak concurrent connections: 142
"""


def _running_config(shell, args): return RUNNING_CONFIG
def _vpn_sessiondb(shell, args): return SHOW_VPN_SESSIONDB
def _logging(shell, args): return SHOW_LOGGING
def _tunnel_group_info(shell, args): return SHOW_TUNNEL_GROUP_INFO
def _webvpn_stats(shell, args): return SHOW_WEBVPN_STATS


def _enable(shell, args):
    if shell.mode != "user": return ""
    sys.stdout.write("Password: "); sys.stdout.flush()
    try: line = sys.stdin.readline().rstrip("\n")
    except (KeyboardInterrupt, EOFError): print(); return ""
    if line == ENABLE_PASSWORD:
        shell.mode = "privileged"; return ""
    return "% Access denied\n"


def _disable(shell, args):
    if shell.mode in ("privileged", "config"): shell.mode = "user"
    return ""


def _configure_terminal(shell, args):
    shell.mode = "config"; return ""


def _end(shell, args):
    if shell.mode == "config": shell.mode = "privileged"
    return ""


def _exit(shell, args):
    if shell.mode == "config": shell.mode = "privileged"; return ""
    if shell.mode == "privileged": shell.mode = "user"; return ""
    print("\nConnection closed by foreign host."); raise SystemExit


def _noop(shell, args): return ""


GRAMMAR = {
    "show": {
        "running-config": {"fn": _running_config, "min_mode": "privileged"},
        # vpn-sessiondb handler is permissive — accepts trailing
        # `anyconnect` / `summary` / `index N` filters that the
        # real ASA supports; we just dump the full table.
        "vpn-sessiondb": {"fn": _vpn_sessiondb},
        "logging": {"fn": _logging, "min_mode": "privileged"},
        "tunnel-group-info": {"fn": _tunnel_group_info},
        "webvpn": {"statistics": {"fn": _webvpn_stats}},
    },
    "enable": {"fn": _enable},
    "disable": {"fn": _disable},
    "configure": {"terminal": {"fn": _configure_terminal, "min_mode": "privileged"}},
    "end": {"fn": _end, "min_mode": "config"},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
    "terminal": {"pager": {"fn": _noop}},
}
