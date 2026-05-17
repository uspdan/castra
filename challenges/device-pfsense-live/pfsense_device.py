"""pfSense 2.7.0-RELEASE device data + grammar for pfsense-edge-01.

Backdrop: WebGUI was exposed on WAN with a guessable admin password
(common ICS / SMB pattern). Attacker brute-forced, logged in,
added a backdoor admin and a NAT rule that exposes an internal
host on a high WAN port.

This sim wraps the most useful pfSense forensics surfaces — the
``/conf/config.xml`` user / NAT / firewall sections, plus
authentication and filter logs — as ``show`` commands. (Real
pfSense reaches these via the console menu option 8 "Shell" then
``pfctl`` / ``cat`` / ``grep``; this sim collapses that into a
single CLI for the exercise.)
"""

from __future__ import annotations

import sys

HOSTNAME = "pfsense-edge-01"

BANNER = """*** Welcome to pfSense 2.7.0-RELEASE (amd64) on pfsense-edge-01 ***

  WAN (wan)        -> em0       -> v4: 192.0.2.18/30
  LAN (lan)        -> em1       -> v4: 10.10.0.1/24

"""

AUTH_BANNER = "\n"
AUTH_USERNAME_PROMPT = "{hostname} login: "
AUTH_PASSWORD_PROMPT = "Password: "

PROMPT_SUFFIXES = {"user": "> "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"{host}{suffix}"


SHOW_VERSION = """2.7.0-RELEASE
Built on Wed Jun 28 03:30:00 EDT 2023
FreeBSD 14.0-CURRENT
"""

SHOW_USERS = """  uid=0   name=admin       groupname=admins
          fullname="System Administrator"
          authorizedkeys=""

  uid=2000 name=noc-readonly groupname=guests
          fullname="NMS read-only account"

  uid=2099 name=REDACTED   groupname=admins
          fullname="WebGUI-added 2026-05-15 03:11"
"""

SHOW_CONFIG = """<?xml version="1.0"?>
<pfsense>
  <version>22.7</version>
  <hostname>pfsense-edge-01</hostname>
  <system>
    <user>
      <name>admin</name>
      <descr>System Administrator</descr>
      <scope>system</scope>
      <groupname>admins</groupname>
      <password>$2y$10$ADMINredacted</password>
      <uid>0</uid>
    </user>
    <user>
      <name>noc-readonly</name>
      <descr>NMS read-only account</descr>
      <scope>user</scope>
      <groupname>guests</groupname>
      <password>$2y$10$NOCredacted</password>
      <uid>2000</uid>
    </user>
    <user>
      <name>REDACTED</name>
      <descr>WebGUI-added 2026-05-15 03:11</descr>
      <scope>user</scope>
      <groupname>admins</groupname>
      <password>$2y$10$ROGUEredacted</password>
      <uid>2099</uid>
    </user>
    <webgui>
      <protocol>https</protocol>
      <port>443</port>
      <interfaces>wan,lan</interfaces>
    </webgui>
  </system>
  <nat>
    <rule>
      <descr>REDACTED</descr>
      <interface>wan</interface>
      <protocol>tcp</protocol>
      <source><any/></source>
      <destination>
        <network>wanip</network>
        <port>REDACTED</port>
      </destination>
      <target>REDACTED</target>
      <local-port>22</local-port>
    </rule>
  </nat>
</pfsense>
"""

SHOW_RULES = """No ALTQ support in kernel
ALTQ related functions disabled

block return-rst log quick on em0 inet proto tcp from <bogons> to (em0)
pass in log quick on em0 reply-to (em0 192.0.2.17) inet proto tcp from any to 192.0.2.18 port REDACTED keep state label "USER_RULE: REDACTED"
pass in quick on em1 inet from 10.10.0.0/24 to any keep state
block drop log quick inet from <virusprot> to any label "virusprot"
"""

SHOW_NAT = """rdr on em0 inet proto tcp from any to 192.0.2.18 port = REDACTED -> REDACTED port 22
nat on em0 inet from 10.10.0.0/24 to any -> (em0:0)
"""

SHOW_AUTH_LOG = """May 15 03:08:11 pfsense-edge-01 nginx: 2026/05/15 03:08:11 [error] 9241#100120: *12 user 'admin' authentication failed, client: REDACTED
May 15 03:08:14 pfsense-edge-01 nginx: 2026/05/15 03:08:14 [error] 9241#100120: *13 user 'admin' authentication failed, client: REDACTED
May 15 03:08:18 pfsense-edge-01 nginx: 2026/05/15 03:08:18 [error] 9241#100120: *14 user 'admin' authentication failed, client: REDACTED
... 198 more failures elided ...
May 15 03:10:48 pfsense-edge-01 nginx: 2026/05/15 03:10:48 [info] 9241#100120: *217 user 'admin' authenticated successfully, client: REDACTED
May 15 03:11:22 pfsense-edge-01 webconfigurator: Successful login for user 'admin' from: REDACTED (Local Database)
May 15 03:11:32 pfsense-edge-01 webconfigurator: Successful change of user 'REDACTED' (added) by user 'admin' from: REDACTED
May 15 03:13:55 pfsense-edge-01 webconfigurator: Successful change of NAT rule 'REDACTED' (added) by user 'REDACTED' from: REDACTED
"""

SHOW_LOG_FILTER = """May 15 03:13:58 pfsense-edge-01 filterlog: 14,,,1000000103,em0,match,pass,in,4,0x0,,64,42891,0,DF,6,tcp,60,REDACTED,192.0.2.18,52144,REDACTED,0,S,...
May 15 03:14:01 pfsense-edge-01 filterlog: 14,,,1000000103,em0,match,pass,in,4,0x0,,64,42892,0,DF,6,tcp,60,REDACTED,192.0.2.18,52145,REDACTED,0,S,...
May 15 03:14:11 pfsense-edge-01 filterlog: 14,,,1000000103,em0,match,pass,in,4,0x0,,64,42893,0,DF,6,tcp,60,REDACTED,192.0.2.18,52146,REDACTED,0,S,...
"""

SHOW_LOG_SYSTEM = """May 15 03:11:32 pfsense-edge-01 php-fpm[19044]: /system_usermanager.php: Successful login for user 'admin' from: REDACTED (Local Database)
May 15 03:11:32 pfsense-edge-01 php-fpm[19044]: /system_usermanager.php: Successful change of user 'REDACTED' (added)
May 15 03:13:55 pfsense-edge-01 php-fpm[19044]: /firewall_nat_edit.php: Added NAT rule 'REDACTED' (port REDACTED -> REDACTED:22)
"""


def _version(s, a): return SHOW_VERSION
def _users(s, a): return SHOW_USERS
def _config(s, a): return SHOW_CONFIG
def _rules(s, a): return SHOW_RULES
def _nat(s, a): return SHOW_NAT
def _auth_log(s, a): return SHOW_AUTH_LOG
def _log_filter(s, a): return SHOW_LOG_FILTER
def _log_system(s, a): return SHOW_LOG_SYSTEM


def _exit(s, a):
    print(); raise SystemExit


GRAMMAR = {
    "show": {
        "version": {"fn": _version},
        "users": {"fn": _users},
        "config": {"fn": _config},
        "rules": {"fn": _rules},
        "nat": {"fn": _nat},
        "auth-log": {"fn": _auth_log},
        "log": {
            "filter": {"fn": _log_filter},
            "system": {"fn": _log_system},
        },
    },
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
    "logout": {"fn": _exit},
}
