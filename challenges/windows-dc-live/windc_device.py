"""Windows Server 2022 / AD DS device data + grammar for
DC01.corp.local.

Backdrop: textbook Kerberoast → crack → logon → DCSync → privilege
persistence chain. The on-DC forensics signal is a mix of AD
object state (an account with an SPN, a rogue REDACTED
member) and REDACTED event log entries (4769 ticket requests,
4624 logons, REDACTED with the DS-Replication-Get-Changes GUID, 4732
group-membership change).

The shell engine is reused unchanged — cmdlets are single tokens
that resolve at the top level, handlers ignore the trailing
``-Param Value`` shape, and ``| include`` / ``| match`` / ``|
count`` work as a stand-in for ``Where-Object`` / ``Measure-Object``
on the grep paths the player needs.
"""

from __future__ import annotations

import sys

HOSTNAME = "DC01"

BANNER = """Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

Try the new cross-platform PowerShell https://aka.ms/pscore6

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "User name: "
AUTH_PASSWORD_PROMPT = "Password: "

# PowerShell prompt — no mode hierarchy; single prompt level.
PROMPT_SUFFIXES = {"user": "> "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"PS C:\\Users\\Administrator{suffix}"


# ---------------------------------------------------------------------------
# Canned outputs
# ---------------------------------------------------------------------------

GET_ADUSER_FILTER_STAR = """DistinguishedName : CN=Administrator,CN=Users,DC=corp,DC=local
Enabled           : True
GivenName         : Administrator
Name              : Administrator
SamAccountName    : administrator

DistinguishedName : CN=netops,CN=Users,DC=corp,DC=local
Enabled           : True
SamAccountName    : netops

DistinguishedName : CN=REDACTED,OU=Service Accounts,DC=corp,DC=local
Enabled           : True
SamAccountName    : REDACTED
ServicePrincipalName : {REDACTED, MSSQLSvc/sql-prod.corp.local}
PasswordLastSet   : 2023-08-12 10:00:00

DistinguishedName : CN=svc-backup,OU=Service Accounts,DC=corp,DC=local
Enabled           : True
SamAccountName    : svc-backup
ServicePrincipalName : {}

DistinguishedName : CN=REDACTED-temp,OU=Service Accounts,DC=corp,DC=local
Enabled           : True
SamAccountName    : REDACTED-temp
PasswordLastSet   : 2026-05-17 03:14:22
"""

GET_ADGROUPMEMBER_DA = """name              SamAccountName  ObjectClass  DistinguishedName
----              --------------  -----------  -----------------
Administrator     Administrator   user         CN=Administrator,CN=Users,DC=corp,DC=local
netops            netops          user         CN=netops,CN=Users,DC=corp,DC=local
REDACTED-temp      REDACTED-temp    user         CN=REDACTED-temp,OU=Service Accounts,DC=corp,DC=local
"""

GET_ADCOMPUTER = """Name             OperatingSystem               DNSHostName
----             ---------------               -----------
DC01             Windows Server 2022 Standard   DC01.corp.local
FS-CORP-01       Windows Server 2022 Standard   FS-CORP-01.corp.local
WS-FIN-04        Windows 11 Enterprise          WS-FIN-04.corp.local
SQL-PROD         Windows Server 2019 Standard   SQL-PROD.corp.local
"""

GET_ADOBJECT_ADMINSDHOLDER = """DistinguishedName : CN=AdminSDHolder,CN=System,DC=corp,DC=local
ntREDACTEDDescriptor : System.DirectoryServices.ActiveDirectoryREDACTED

Access Control List:
  IdentityReference     AccessControlType  ActiveDirectoryRights
  --------------------  -----------------  ----------------------
  CORP\\REDACTED   Allow              GenericAll
  CORP\\Enterprise Admins Allow            GenericAll
  CORP\\REDACTED-temp    Allow              WriteDACL, WriteOwner
  NT AUTHORITY\\SYSTEM  Allow              GenericAll
"""

GET_WINEVENT_SECURITY = """ProviderName: Microsoft-Windows-REDACTED-Auditing

TimeCreated                Id LevelDisplayName Message
-----------                -- ---------------- -------
2026-05-17 03:08:11.121     4769 Information   A Kerberos service ticket was requested. Account Name: bob@corp.local; Service Name: REDACTED; Client Address: ::ffff:REDACTED; Ticket Encryption Type: 0x17
2026-05-17 03:08:13.402     4769 Information   A Kerberos service ticket was requested. Account Name: bob@corp.local; Service Name: REDACTED; Client Address: ::ffff:REDACTED; Ticket Encryption Type: 0x17
2026-05-17 03:08:14.811     4769 Information   A Kerberos service ticket was requested. Account Name: bob@corp.local; Service Name: REDACTED; Client Address: ::ffff:REDACTED; Ticket Encryption Type: 0x17
2026-05-17 03:10:48.117     4624 Information   An account was successfully logged on. Logon Type: 3 (Network). Account Name: REDACTED; Source Network Address: REDACTED; Source Port: 52144; Authentication Package: Kerberos
2026-05-17 03:11:22.880     REDACTED Information   An operation was performed on an object. Object Type: %{19195a5b-6da0-11d0-afd3-00c04fd930c9}; Properties: %{1131f6aa-9c07-11d1-f79f-00c04fc2dcd2} %{1131f6ad-9c07-11d1-f79f-00c04fc2dcd2}; Subject: REDACTED
2026-05-17 03:11:24.222     REDACTED Information   An operation was performed on an object. Properties: %{1131f6ad-9c07-11d1-f79f-00c04fc2dcd2}; Subject: REDACTED
2026-05-17 03:13:19.422     4720 Information   A user account was created. Account Name: REDACTED-temp; Subject: REDACTED
2026-05-17 03:13:55.107     4732 Information   A member was added to a security-enabled local group. Member: REDACTED-temp; Group Name: REDACTED; Subject: REDACTED
2026-05-17 03:14:22.560     4738 Information   A user account was changed. Account Name: REDACTED-temp; Subject: REDACTED
"""

GET_REDACTEDUSER = """Name             Enabled Description
----             ------- -----------
Administrator    True    Built-in account for administering the computer/domain
DefaultAccount   False   A user account managed by the system.
Guest            False   Built-in account for guest access to the computer/domain
WDAGUtilityAccount False
"""

GET_PROCESS = """Handles  NPM(K)    PM(K)      WS(K)     CPU(s)     Id  ProcessName
-------  ------    -----      -----     ------     --  -----------
    411      18    25340       7212       2.41    412  dns
    832      24    18244       5912       1.18    524  lsass
    188      11     2884       1632       0.04    448  spoolsv
    411      14    18412       6512       0.78   2104  MsMpEng
    188      12     2440       1248       0.02   4592  svchost
"""

GET_SCHEDULEDTASK = """TaskPath                                       TaskName                          State
--------                                       --------                          -----
\\Microsoft\\Windows\\AD RMS Rights Policy...   Update RMS                         Ready
\\Microsoft\\Windows\\Defrag\\                  ScheduledDefrag                    Ready
\\Microsoft\\Windows\\TaskScheduler\\           Idle Maintenance                   Ready
"""

WHOAMI_PRIV = """PRIVILEGES INFORMATION
----------------------

Privilege Name                Description                          State
============================= ==================================== ========
SeREDACTEDPrivilege           Manage auditing and security log     Enabled
SeBackupPrivilege             Back up files and directories        Enabled
SeRestorePrivilege            Restore files and directories        Enabled
SeSystemtimePrivilege         Change the system time               Enabled
SeShutdownPrivilege           Shut down the system                 Enabled
SeIncreaseQuotaPrivilege      Adjust memory quotas for a process   Enabled
SeTakeOwnershipPrivilege      Take ownership of files or other     Enabled
"""

WHOAMI = "corp\\administrator\n"


def _adusers(s, a): return GET_ADUSER_FILTER_STAR
def _adgroup(s, a): return GET_ADGROUPMEMBER_DA
def _adcomputer(s, a): return GET_ADCOMPUTER
def _adobject(s, a): return GET_ADOBJECT_ADMINSDHOLDER
def _winevent(s, a): return GET_WINEVENT_SECURITY
def _localuser(s, a): return GET_REDACTEDUSER
def _processes(s, a): return GET_PROCESS
def _scheduledtask(s, a): return GET_SCHEDULEDTASK


def _whoami(s, a):
    # If `-Priv` / `/priv` somewhere in args, give the priv table; else the name.
    if any("priv" in tok.lower() for tok in (a or [])):
        return WHOAMI_PRIV
    return WHOAMI


def _exit(s, a):
    print(); raise SystemExit


def _noop(s, a):
    # Where-Object / Select-Object / Format-Table as no-ops — players who
    # type PowerShell-style pipes still get useful output, while the
    # engine's native `| include` does the real filtering.
    return ""


GRAMMAR = {
    "get-aduser": {"fn": _adusers},
    "get-adgroupmember": {"fn": _adgroup},
    "get-adcomputer": {"fn": _adcomputer},
    "get-adobject": {"fn": _adobject},
    "get-winevent": {"fn": _winevent},
    "get-eventlog": {"fn": _winevent},
    "get-localuser": {"fn": _localuser},
    "get-process": {"fn": _processes},
    "get-scheduledtask": {"fn": _scheduledtask},
    "whoami": {"fn": _whoami},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
    "logout": {"fn": _exit},
}
