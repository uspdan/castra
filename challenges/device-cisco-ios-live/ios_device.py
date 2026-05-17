"""Cisco IOS 15.7 device data + grammar for BR-EDGE-01.

The shell engine (shell.py) imports this module and treats:
  HOSTNAME, BANNER, GRAMMAR, PRELOADED_HISTORY
as the contract. Everything else here is private state for the
handler functions defined below.
"""

from __future__ import annotations

import sys

HOSTNAME = "BR-EDGE-01"

BANNER = """Trying 127.0.0.1...
Connected to br-edge-01.
Escape character is '^]'.

! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! !
! UNAUTHORISED ACCESS PROHIBITED.                            !
! Activity on this device is logged and monitored.           !
! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! ! !
"""

ENABLE_PASSWORD = "n0c-l3v3l-15"

# ---------------------------------------------------------------------------
# Pre-baked outputs. Order matters for some (running-config block layout
# matches what a real `show run` would emit for this device).
# ---------------------------------------------------------------------------

RUNNING_CONFIG = """Building configuration...

Current configuration : 2418 bytes
!
! Last configuration change at 03:14:22 UTC Wed May 14 2026 by REDACTED
! NVRAM config last updated at 03:15:01 UTC Wed May 14 2026 by REDACTED
!
version 15.7
service timestamps debug datetime msec
service timestamps log datetime msec
service password-encryption
!
hostname BR-EDGE-01
!
boot-start-marker
boot system flash:c2900-universalk9-mz.SPA.157-3.M5.bin
boot-end-marker
!
aaa new-model
aaa authentication login default local
aaa authorization exec default local
!
enable secret 8 $8$abcdef...redacted
!
username netops privilege 15 secret 8 $8$opsaccount...redacted
username monitor privilege 5  secret 8 $8$readonly...redacted
username REDACTED privilege 15 secret 8 $8$z9c1f-newpwd-redacted
!
ip access-list extended ACL-OUT
!
snmp-server community READ-ONLY RO
snmp-server community REDACTED RW
snmp-server location DC1-rack-12
!
interface GigabitEthernet0/0
 description WAN
 ip address 192.0.2.18 255.255.255.252
 ip access-group 102 out
 no shutdown
!
interface GigabitEthernet0/1
 description LAN
 ip address 10.10.0.1 255.255.255.0
 ip access-group 101 in
 no shutdown
!
interface Tunnel0
 description maintenance-link
 ip address 192.168.244.1 255.255.255.252
 tunnel source GigabitEthernet0/0
 tunnel destination REDACTED
 tunnel mode gre ip
!
access-list 101 permit ip 10.10.0.0 0.0.0.255 any
access-list 101 deny ip any any log
!
access-list 102 permit ip 10.10.0.0 0.0.0.255 198.51.100.0 0.0.0.255
access-list 102 permit ip any host 8.8.8.8
access-list 102 permit ip any host 1.1.1.1
access-list 102 deny ip any any log
!
line vty 0 4
 transport input ssh
 login authentication default
!
ip http server
ip http secure-server
!
end
"""

SHOW_USERS = """    Line       User       Host(s)              Idle       Location
   0 con 0                idle                 00:42:11
*  1 vty 0   REDACTED      idle                 00:00:08   REDACTED
   2 vty 1                idle                 -
   3 vty 2                idle                 -

  Interface    User               Mode         Idle     Peer Address
"""

SHOW_SNMP = """Chassis: FTX1745A0B8
Contact: noc@example.com
Location: DC1-rack-12

SNMP packets input
    12483921 - get-request packets
    482011  - get-next packets
    1820    - set-request packets

SNMP packets output
    12483921 - response packets
    0       - trap packets

SNMP communities:
    READ-ONLY        RO
    REDACTED        RW

SNMP global trap: disabled
"""

SHOW_LOGGING = """Syslog logging: enabled (0 messages dropped, 4 messages rate-limited)

Console logging: level debugging, 23012 messages logged, xml disabled
Monitor logging: level debugging, 0 messages logged, xml disabled
Buffer logging:  level debugging, 28213 messages logged, xml disabled
Logging Exception size (4096 bytes)
Trap logging: level informational, 28013 message lines logged
    Logging to 10.10.0.50  (udp port 514, audit disabled, link up),
        0 message lines logged, 0 messages rate-limited, 0 messages dropped (UDP queue overflow)

Log Buffer (8192 bytes):

May 14 03:08:11.121 UTC: %SNMP-3-AUTHFAIL: Authentication failure for SNMP req from REDACTED
May 14 03:08:14.402 UTC: %SNMP-3-AUTHFAIL: Authentication failure for SNMP req from REDACTED
May 14 03:08:18.811 UTC: %SNMP-3-AUTHFAIL: Authentication failure for SNMP req from REDACTED
May 14 03:09:02.044 UTC: %SNMP-5-COLDSTART: SNMP agent on host BR-EDGE-01 is undergoing a cold start
May 14 03:09:48.117 UTC: %SEC_LOGIN-5-LOGIN_SUCCESS: Login Success [user: REDACTED] [Source: REDACTED] [localport: 22] at 03:09:48 UTC Wed May 14 2026
May 14 03:11:22.880 UTC: %SYS-5-CONFIG_I: Configured from console by REDACTED on vty0 (REDACTED)
May 14 03:13:19.422 UTC: %LINK-3-UPDOWN: Interface Tunnel0, changed state to up
May 14 03:13:20.001 UTC: %LINEPROTO-5-UPDOWN: Line protocol on Interface Tunnel0, changed state to up
May 14 03:14:22.107 UTC: %SYS-5-CONFIG_I: Configured from console by REDACTED on vty0 (REDACTED)
May 14 03:15:01.560 UTC: %SYS-6-LOGGINGHOST_STARTSTOP: Logging to host 10.10.0.50 stopped - CLI initiated
"""

SHOW_VERSION = """Cisco IOS Software, C2900 Software (C2900-UNIVERSALK9-M), Version 15.7(3)M5, RELEASE SOFTWARE (fc4)
Technical Support: http://www.cisco.com/techsupport
Copyright (c) 1986-2019 by Cisco Systems, Inc.
Compiled Wed 23-Jan-19 23:42 by prod_rel_team

ROM: System Bootstrap, Version 15.0(1r)M15, RELEASE SOFTWARE (fc1)

BR-EDGE-01 uptime is 142 days, 4 hours, 11 minutes
System returned to ROM by power-on
System restarted at 03:09:02 UTC Wed May 14 2026
System image file is "flash:c2900-universalk9-mz.SPA.157-3.M5.bin"

Cisco CISCO2911/K9 (revision 1.0) with 491520K/32768K bytes of memory.
Processor board ID FTX1745A0B8
3 Gigabit Ethernet interfaces
1 terminal line
DRAM configuration is 64 bits wide with parity disabled.
255K bytes of non-volatile configuration memory.
255488K bytes of ATA System CompactFlash 0 (Read/Write)

License Info:
Technology Package License Information for Module:'c2900'

Configuration register is 0x2102
"""

SHOW_IP_INTERFACE_BRIEF = """Interface                  IP-Address      OK? Method Status                Protocol
GigabitEthernet0/0         192.0.2.18      YES NVRAM  up                    up
GigabitEthernet0/1         10.10.0.1       YES NVRAM  up                    up
GigabitEthernet0/2         unassigned      YES NVRAM  administratively down down
Tunnel0                    192.168.244.1   YES NVRAM  up                    up
"""

SHOW_IP_ROUTE = """Codes: L - local, C - connected, S - static, R - RIP, M - mobile, B - BGP
       D - EIGRP, EX - EIGRP external, O - OSPF, IA - OSPF inter area
       N1 - OSPF NSSA external type 1, N2 - OSPF NSSA external type 2
       E1 - OSPF external type 1, E2 - OSPF external type 2
       i - IS-IS, su - IS-IS summary, L1 - IS-IS level-1, L2 - IS-IS level-2
       ia - IS-IS inter area, * - candidate default, U - per-user static route
       o - ODR, P - periodic downloaded static route, + - replicated route
       % - next hop override, p - overrides from PfR

Gateway of last resort is 192.0.2.17 to network 0.0.0.0

S*    0.0.0.0/0 [1/0] via 192.0.2.17
      10.0.0.0/24 is subnetted, 1 subnets
C        10.10.0.0/24 is directly connected, GigabitEthernet0/1
L        10.10.0.1/32 is directly connected, GigabitEthernet0/1
      192.0.2.0/30 is subnetted, 1 subnets
C        192.0.2.16/30 is directly connected, GigabitEthernet0/0
L        192.0.2.18/32 is directly connected, GigabitEthernet0/0
      192.168.244.0/30 is subnetted, 1 subnets
C        192.168.244.0/30 is directly connected, Tunnel0
L        192.168.244.1/32 is directly connected, Tunnel0
S     REDACTED [1/0] via 192.168.244.2, Tunnel0
"""

SHOW_ACL = """Extended IP access list 101
    10 permit ip 10.10.0.0 0.0.0.255 any (1842 matches)
    20 deny   ip any any log
Extended IP access list 102
    10 permit ip 10.10.0.0 0.0.0.255 198.51.100.0 0.0.0.255 (88241 matches)
    20 permit ip any host 8.8.8.8 (102 matches)
    30 permit ip any host 1.1.1.1 (44 matches)
    40 deny   ip any any log
"""

# The last user (the attacker, REDACTED on vty 0) left this in
# their per-line history buffer. `show history` prints it.
PRELOADED_HISTORY = [
    "enable",
    "configure terminal",
    "username REDACTED privilege 15 secret 0 z9c1f-newpwd",
    "snmp-server community REDACTED RW",
    "interface Tunnel0",
    " ip address 192.168.244.1 255.255.255.252",
    " tunnel source GigabitEthernet0/0",
    " tunnel destination REDACTED",
    " tunnel mode gre ip",
    " no shutdown",
    "exit",
    "access-list 102 permit ip 10.10.0.0 0.0.0.255 198.51.100.0 0.0.0.255",
    "no logging host 10.10.0.50",
    "end",
    "write memory",
]


# ---------------------------------------------------------------------------
# Handlers — (shell, remaining_tokens) -> output string
# ---------------------------------------------------------------------------

def _running_config(shell, args):
    return RUNNING_CONFIG


def _users(shell, args):
    return SHOW_USERS


def _snmp(shell, args):
    return SHOW_SNMP


def _logging(shell, args):
    return SHOW_LOGGING


def _version(shell, args):
    return SHOW_VERSION


def _ip_int_brief(shell, args):
    return SHOW_IP_INTERFACE_BRIEF


def _ip_route(shell, args):
    return SHOW_IP_ROUTE


def _acl(shell, args):
    return SHOW_ACL


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
    if shell.mode == "privileged":
        shell.mode = "user"
    elif shell.mode == "config":
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
        shell.mode = "privileged"
        return ""
    if shell.mode == "privileged":
        shell.mode = "user"
        return ""
    print("\nConnection closed by foreign host.")
    raise SystemExit


def _noop(shell, args):
    return ""


def _write_memory(shell, args):
    return "Building configuration...\n[OK]\n"


# ---------------------------------------------------------------------------
# Grammar
# ---------------------------------------------------------------------------

GRAMMAR = {
    "show": {
        "running-config": {"fn": _running_config, "min_mode": "privileged"},
        "startup-config": {"fn": _running_config, "min_mode": "privileged"},
        "users": {"fn": _users},
        "snmp": {"fn": _snmp},
        "logging": {"fn": _logging, "min_mode": "privileged"},
        "version": {"fn": _version},
        "ip": {
            "interface": {"brief": {"fn": _ip_int_brief}},
            "route": {"fn": _ip_route},
        },
        "access-lists": {"fn": _acl},
        "history": {"fn": _history},
    },
    "enable": {"fn": _enable},
    "disable": {"fn": _disable},
    "configure": {"terminal": {"fn": _configure_terminal, "min_mode": "privileged"}},
    "end": {"fn": _end, "min_mode": "config"},
    "exit": {"fn": _exit},
    "logout": {"fn": _exit},
    "quit": {"fn": _exit},
    "write": {"memory": {"fn": _write_memory, "min_mode": "privileged"}},
    "terminal": {
        "length": {"fn": _noop},
        "monitor": {"fn": _noop},
        "no": {"monitor": {"fn": _noop}},
    },
}
