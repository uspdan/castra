"""Cisco IOS XE 17.9 device data + grammar for IOSXE-EDGE-01.

Backdrop: CVE-2023-20198 (October 2023). Unauthenticated attackers
abused the IOS XE web UI to create a privilege-15 local account,
then followed up with CVE-2023-20273 to drop a Lua implant served
via the on-box nginx. Public Talos/Cisco PSIRT write-ups document
the exact pattern.

The classic on-box forensics signal: a new local user with
``privilege 15``, and a running-config that has the
``ip http server`` / ``ip http secure-server`` lines that the
attacker required.
"""

from __future__ import annotations

import sys

HOSTNAME = "IOSXE-EDGE-01"

BANNER = """Trying 127.0.0.1...
Connected to iosxe-edge-01.
Escape character is '^]'.

UNAUTHORISED ACCESS PROHIBITED.
"""

ENABLE_PASSWORD = "n0c-l3v3l-15"

RUNNING_CONFIG = """Building configuration...

Current configuration : 4218 bytes
!
! Last configuration change at 03:14:22 UTC Sat Oct 14 2023 by REDACTED
!
version 17.9
hostname IOSXE-EDGE-01
!
boot system flash bootflash:c8000be-universalk9.17.09.01a.SPA.bin
!
aaa new-model
aaa authentication login default local
aaa authorization exec default local
!
enable secret 8 $8$ENABLE...redacted
!
username netops privilege 15 secret 8 $8$NETOPS...redacted
username monitor privilege 5  secret 8 $8$MONITOR...redacted
username REDACTED privilege 15 secret 8 $8$ROGUE...redacted
!
ip http server
ip http secure-server
ip http authentication local
!
interface GigabitEthernet0/0/0
 description WAN
 ip address 192.0.2.18 255.255.255.252
 no shutdown
!
interface GigabitEthernet0/0/1
 description LAN
 ip address 10.10.0.1 255.255.255.0
 no shutdown
!
line vty 0 4
 transport input ssh
 login authentication default
!
end
"""

SHOW_USERS = """    Line       User                Host(s)              Idle       Location
   0 con 0                          idle                 00:42:11
*  1 vty 0   REDACTED        idle                 00:00:08   REDACTED
   2 vty 1                          idle                 -
"""

SHOW_VERSION = """Cisco IOS XE Software, Version 17.09.01a
Cisco IOS Software [Cupertino], Catalyst L3 Switch Software (CAT9K_IOSXE), Version 17.9.1a, RELEASE SOFTWARE (fc4)
Technical Support: http://www.cisco.com/techsupport
Copyright (c) 1986-2022 by Cisco Systems, Inc.
Compiled Sat 16-Jul-22 03:42 by mcpre

IOSXE-EDGE-01 uptime is 1 year, 7 months, 4 days
Uptime for this control processor is 1 year, 7 months, 4 days
System returned to ROM by reload at 14:00:08 UTC Wed Sep 13 2022
System image file is "bootflash:c8000be-universalk9.17.09.01a.SPA.bin"
Last reload reason: Reload Command

Configuration register is 0x2102
"""

SHOW_LOGGING = """Syslog logging: enabled (0 messages dropped)
Trap logging: level informational, 28013 message lines logged
Buffer logging:  level debugging, 28213 messages logged

Log Buffer (8192 bytes):

Oct 14 03:08:11.121 UTC: %WEBUI-6-INSTALL_OPERATION_INFO: Received request from REDACTED - /webui/logoutconfirm.html?logon_hash=1
Oct 14 03:08:14.402 UTC: %WEBUI-6-INSTALL_OPERATION_INFO: Received request from REDACTED - REDACTED
Oct 14 03:08:18.811 UTC: %WEBUI-5-USER_ADDED: User "REDACTED" added by user "REDACTED" via http_admin
Oct 14 03:09:48.117 UTC: %SEC_LOGIN-5-LOGIN_SUCCESS: Login Success [user: REDACTED] [Source: REDACTED] [localport: 22]
Oct 14 03:11:22.880 UTC: %SYS-5-CONFIG_I: Configured from console by REDACTED on vty0 (REDACTED)
Oct 14 03:13:19.422 UTC: %WEBUI-5-FILE_ADDED: File /flash/nginx-conf/REDACTED.conf created (size=412) by REDACTED
Oct 14 03:14:22.107 UTC: %SYS-5-CONFIG_I: Configured from console by REDACTED on vty0 (REDACTED)
Oct 14 03:15:01.560 UTC: %SYS-6-LOGGINGHOST_STARTSTOP: Logging to host 10.10.0.50 stopped - CLI initiated
"""

SHOW_IP_HTTP_SERVER_STATUS = """HTTP server status: Enabled
HTTP server port: 80
HTTP secure server status: Enabled
HTTP secure server port: 443
HTTP secure server ciphersuite: rsa-aes-cbc-sha2 rsa-aes-gcm-sha2

Internal listener bound by nginx (post-2026-10-14 module reload):
  Port REDACTED  - REDACTED.conf  (module: lua-implant)
"""

SHOW_PLATFORM_SOFTWARE_PROCESS = """Process information for FP_0
Name           PID    Status   Size     CPU%   Description
nginx          14411  R        12340    0.4    Embedded web server
REDACTED  14422  R        4096     0.1    Custom WSMA module (uid=root)
linux_iosd-im  2104   S        285012   2.1    IOS daemon
"""

WEBUI_ACCESS_LOG = """REDACTED - - [14/Oct/2023:03:08:11 +0000] "GET /webui/logoutconfirm.html?logon_hash=1 HTTP/1.1" 200 26 "-" "python-requests/2.31.0"
REDACTED - - [14/Oct/2023:03:08:14 +0000] "POST REDACTED HTTP/1.1" 200 4218 "-" "python-requests/2.31.0"
REDACTED - - [14/Oct/2023:03:08:18 +0000] "POST /webui/rest/onep/users HTTP/1.1" 200 412 "-" "python-requests/2.31.0"
REDACTED - - [14/Oct/2023:03:13:19 +0000] "POST /webui/rest/onep/files HTTP/1.1" 200 88 "-" "python-requests/2.31.0"
"""

PRELOADED_HISTORY = [
    "enable",
    "configure terminal",
    "username REDACTED privilege 15 secret 0 r0gu3-pwd",
    "ip http server",
    "ip http secure-server",
    "exit",
    "copy bootflash:REDACTED.conf running",
    "no logging host 10.10.0.50",
    "end",
    "write memory",
]


def _running_config(shell, args):
    return RUNNING_CONFIG


def _users(shell, args):
    return SHOW_USERS


def _version(shell, args):
    return SHOW_VERSION


def _logging(shell, args):
    return SHOW_LOGGING


def _ip_http_server(shell, args):
    return SHOW_IP_HTTP_SERVER_STATUS


def _platform_processes(shell, args):
    return SHOW_PLATFORM_SOFTWARE_PROCESS


def _webui_log(shell, args):
    return WEBUI_ACCESS_LOG


def _history(shell, args):
    return "\n".join(f"  {cmd}" for cmd in shell.history) + "\n"


def _enable(shell, args):
    if shell.mode != "user":
        return ""
    sys.stdout.write("Password: ")
    sys.stdout.flush()
    try:
        line = sys.stdin.readline().rstrip("\n")
    except (KeyboardInterrupt, EOFError):
        print(); return ""
    if line == ENABLE_PASSWORD:
        shell.mode = "privileged"
        return ""
    return "% Access denied\n"


def _disable(shell, args):
    if shell.mode in ("privileged", "config"):
        shell.mode = "user"
    return ""


def _configure_terminal(shell, args):
    shell.mode = "config"
    return "Enter configuration commands, one per line.  End with CNTL/Z.\n"


def _end(shell, args):
    if shell.mode == "config":
        shell.mode = "privileged"
    return ""


def _exit(shell, args):
    if shell.mode == "config":
        shell.mode = "privileged"; return ""
    if shell.mode == "privileged":
        shell.mode = "user"; return ""
    print("\nConnection closed by foreign host."); raise SystemExit


def _noop(shell, args):
    return ""


GRAMMAR = {
    "show": {
        "running-config": {"fn": _running_config, "min_mode": "privileged"},
        "startup-config": {"fn": _running_config, "min_mode": "privileged"},
        "users": {"fn": _users},
        "version": {"fn": _version},
        "logging": {"fn": _logging, "min_mode": "privileged"},
        "ip": {"http": {"server": {"status": {"fn": _ip_http_server}}}},
        "platform": {"software": {"process": {"list": {"fn": _platform_processes}}}},
        "history": {"fn": _history},
        "webui-log": {"fn": _webui_log},
    },
    "enable": {"fn": _enable},
    "disable": {"fn": _disable},
    "configure": {"terminal": {"fn": _configure_terminal, "min_mode": "privileged"}},
    "end": {"fn": _end, "min_mode": "config"},
    "exit": {"fn": _exit},
    "logout": {"fn": _exit},
    "quit": {"fn": _exit},
    "terminal": {
        "length": {"fn": _noop},
        "monitor": {"fn": _noop},
    },
}
