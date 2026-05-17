"""PAN-OS 10.2 device data + grammar for FW-DC-01.

PAN-OS has two modes the player will use:

* **Operational** (``>``) — default. ``show`` / ``debug`` /
  ``ping``. The forensics queries live here.
* **Configure** (``#``) — entered via ``configure``. Lets you
  edit the running config (we expose it for realism but the
  challenge does not require config edits).

Mode mapping: operational → USER, configure → CONFIG. The shell's
PRIV layer is unused for PAN-OS.

The prompt rendering and auth banner are PAN-OS-flavoured via the
shell engine's per-device hooks.
"""

from __future__ import annotations

import sys

HOSTNAME = "FW-DC-01"

BANNER = """Last login: Wed May 14 18:23:11 2026 from 10.10.0.50 on pts/1

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "{hostname} login: "
AUTH_PASSWORD_PROMPT = "Password: "

# Operational > and configure # ; both rendered as "admin@<host>{suffix}".
PROMPT_SUFFIXES = {"user": "> ", "config": "# "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"admin@{host}{suffix}"


# ---------------------------------------------------------------------------
# Canned outputs
# ---------------------------------------------------------------------------

SHOW_SYSTEM_INFO = """hostname: FW-DC-01
ip-address: 10.10.0.1
public-ip-address: 192.0.2.18
netmask: 255.255.255.0
default-gateway: 10.10.0.254
mac-address: 00:1b:17:00:00:01
time: Fri May 15 02:00:01 2026
uptime: 142 days, 4:11:33
family: 3200
model: PA-3220
serial: 013201000123
sw-version: 10.2.0
operational-mode: normal
device-certificate-status: None
"""

SHOW_CONFIG_RUNNING = """<config urldb="paloaltonetworks" version="10.2.0">
  <devices>
    <entry name="localhost.localdomain">
      <vsys>
        <entry name="vsys1">
          <authentication-profile>
            <entry name="gp-employees">
              <method><ldap><server-profile>corp-ldap</server-profile></ldap></method>
              <multi-factor-auth>
                <mfa-enable>yes</mfa-enable>
                <factors><member>okta-push</member></factors>
              </multi-factor-auth>
            </entry>
            <entry name="REDACTED">
              <method><ldap><server-profile>corp-ldap</server-profile></ldap></method>
              <!-- multi-factor-auth removed during change window 2026-03-12 to fix contractor onboarding bug. Was supposed to be reinstated. -->
            </entry>
            <entry name="admin-console">
              <method><saml-idp><server-profile>okta-saml</server-profile></saml-idp></method>
              <multi-factor-auth><mfa-enable>yes</mfa-enable></multi-factor-auth>
            </entry>
          </authentication-profile>
          <rulebase>
            <security>
              <rules>
                <entry name="gp-users-allow-internet">
                  <from><member>gp-tunnel</member></from>
                  <to><member>untrust</member></to>
                  <source><member>any</member></source>
                  <destination><member>any</member></destination>
                  <application><member>any</member></application>
                  <service><member>application-default</member></service>
                  <action>allow</action>
                </entry>
                <entry name="REDACTED">
                  <from><member>gp-tunnel</member></from>
                  <to><member>trust</member></to>
                  <source><member>any</member></source>
                  <destination><member>any</member></destination>
                  <application><member>any</member></application>
                  <service><member>any</member></service>
                  <action>allow</action>
                </entry>
                <entry name="employees-to-mgmt">
                  <from><member>trust</member></from>
                  <to><member>mgmt</member></to>
                  <source><member>employee-workstations</member></source>
                  <destination><member>mgmt-subnet</member></destination>
                  <application><member>ms-rdp</member><member>ssh</member></application>
                  <service><member>application-default</member></service>
                  <action>allow</action>
                </entry>
              </rules>
            </security>
          </rulebase>
        </entry>
      </vsys>
    </entry>
  </devices>
</config>
"""

SHOW_RUNNING_SECURITY_POLICY = """Rule        From  Source  Src-User                  To       Destination     Service  Application  Action  Profile
=========================================================================================================================
gp-users-allow-internet  gp-tunnel  any  any  untrust  any  application-default  any  allow  none
REDACTED  gp-tunnel  any  any  trust    any  any                  any  allow  none
employees-to-mgmt        trust  employee-workstations  any  mgmt  mgmt-subnet  application-default  ms-rdp,ssh  allow  none
"""

SHOW_LOG_GLOBALPROTECT = """2026-05-15T01:42:11Z portal-auth user=REDACTED source-ip=REDACTED auth-profile=REDACTED status=auth-failure reason=invalid-password
2026-05-15T01:42:13Z portal-auth user=REDACTED source-ip=REDACTED auth-profile=REDACTED status=auth-failure reason=invalid-password
2026-05-15T01:42:15Z portal-auth user=REDACTED source-ip=REDACTED auth-profile=REDACTED status=auth-failure reason=invalid-password
2026-05-15T01:42:17Z portal-auth user=REDACTED source-ip=REDACTED auth-profile=REDACTED status=auth-failure reason=invalid-password
... [200+ failures elided] ...
2026-05-15T01:51:33Z portal-auth user=REDACTED source-ip=REDACTED auth-profile=REDACTED status=auth-success reason=local-pw
2026-05-15T01:51:34Z gateway-connect user=REDACTED public-ip=REDACTED tunnel-ip=172.21.4.18 client="GlobalProtect 6.2 Windows" status=connected
"""

SHOW_LOG_TRAFFIC = """Time                  Rule                       Src         Dst            App        Action  Bytes   User
2026-05-15T01:51:55Z  gp-users-allow-internet    172.21.4.18 8.8.8.8        dns        allow   128
2026-05-15T01:52:11Z  gp-users-allow-internet    172.21.4.18 23.45.67.89    ssl        allow   1882
2026-05-15T01:53:04Z  REDACTED    172.21.4.18 10.10.0.50     smb        allow   8420
2026-05-15T01:53:42Z  REDACTED    172.21.4.18 REDACTED    ms-rdp     allow   44288   REDACTED
2026-05-15T01:55:09Z  REDACTED    172.21.4.18 REDACTED    ms-rdp     allow   512042  REDACTED
"""

SHOW_LOG_SYSTEM = """2026-05-15T01:51:33Z severity=informational subtype=auth user=REDACTED event="GlobalProtect portal user authenticated" auth-profile=REDACTED source-ip=REDACTED
2026-05-15T01:51:34Z severity=informational subtype=globalprotect event="user logged in" user=REDACTED portal=gp-portal vsys=vsys1
2026-05-15T01:52:00Z severity=warning       subtype=auth event="rate of failed portal-auth from single source exceeded threshold" source-ip=REDACTED count=237 window=600s
"""

SHOW_GLOBAL_PROTECT_USER = """GlobalProtect Gateway: gp-gateway
Tunnel Name: gp-tunnel
Active Users
============================================================
  Domain   User                  Client                   Public IP        Tunnel IP    Login Time
  CORP     REDACTED      GlobalProtect 6.2 Windows  REDACTED   172.21.4.18  2026-05-15 01:51:34
"""

SHOW_ADMINS = """ admin     web        Active  Last login: Fri May 15 06:55:11 2026 from 10.10.0.50
 sso-admin saml       Idle    Last login: Wed May 13 14:00:22 2026 from 10.10.0.50
"""


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _show_system_info(shell, args):
    return SHOW_SYSTEM_INFO


def _show_config_running(shell, args):
    return SHOW_CONFIG_RUNNING


def _show_running_security_policy(shell, args):
    return SHOW_RUNNING_SECURITY_POLICY


def _show_log_globalprotect(shell, args):
    return SHOW_LOG_GLOBALPROTECT


def _show_log_traffic(shell, args):
    return SHOW_LOG_TRAFFIC


def _show_log_system(shell, args):
    return SHOW_LOG_SYSTEM


def _show_globalprotect_user(shell, args):
    return SHOW_GLOBAL_PROTECT_USER


def _show_admins(shell, args):
    return SHOW_ADMINS


def _configure(shell, args):
    shell.mode = "config"
    return (
        "Entering configuration mode\n"
        "[edit]\n"
    )


def _exit(shell, args):
    if shell.mode == "config":
        shell.mode = "user"
        return "Exiting configuration mode\n"
    sys.stdout.write("\n")
    raise SystemExit


def _commit(shell, args):
    return "Commit job 41 dispatched\nCommit job 41 succeeded.\n"


def _noop(shell, args):
    return ""


# ---------------------------------------------------------------------------
# Grammar — operational mode commands at top level, configure-mode
# commands also exposed (gated on min_mode="config" where it matters).
# ---------------------------------------------------------------------------

GRAMMAR = {
    "show": {
        "system": {"info": {"fn": _show_system_info}},
        "config": {"running": {"fn": _show_config_running}},
        "running": {
            "security-policy": {"fn": _show_running_security_policy},
        },
        "log": {
            "globalprotect": {"fn": _show_log_globalprotect},
            "traffic": {"fn": _show_log_traffic},
            "system": {"fn": _show_log_system},
        },
        "global-protect-gateway": {
            "current-user": {"fn": _show_globalprotect_user},
        },
        "admins": {"fn": _show_admins},
    },
    "configure": {"fn": _configure},
    "commit": {"fn": _commit, "min_mode": "config"},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
    "logout": {"fn": _exit},
    "set": {  # placeholder — config-mode no-op so set commands don't error
        "cli": {"fn": _noop, "min_mode": "config"},
    },
    "request": {  # PAN-OS habit — players sometimes type `request restart`
        "restart": {"fn": _noop},
    },
}
