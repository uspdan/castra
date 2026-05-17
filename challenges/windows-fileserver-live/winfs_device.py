"""Windows Server 2022 file server device data + grammar for
FS-CORP-01.

Backdrop: pre-ransomware lateral movement. Attacker pivoted from
the compromised finance workstation via the user's domain creds,
landed on the file server over SMB / WMI, deleted Volume Shadow
Copies, and staged the encryption pass under ``C:\\Staging\\``
before EDR isolated the host. The on-server signal is the 4624
type-3 logon from the workstation IP, Sysmon process creates for
``REDACTED delete shadows`` and ``REDACTED``, and a brand-new
service installation event.
"""

from __future__ import annotations

import sys

HOSTNAME = "FS-CORP-01"

BANNER = """Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "User name: "
AUTH_PASSWORD_PROMPT = "Password: "

PROMPT_SUFFIXES = {"user": "> "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"PS C:\\Users\\Administrator{suffix}"


# ---------------------------------------------------------------------------
# Canned outputs
# ---------------------------------------------------------------------------

GET_WINEVENT_SECURITY = """ProviderName: Microsoft-Windows-REDACTED-Auditing

TimeCreated                Id  Message
-----------                --  -------
2026-05-15 14:02:11.121   4624 An account was successfully logged on. Logon Type: 3 (Network). Account Name: REDACTED; Source Network Address: REDACTED; Authentication Package: NTLM
2026-05-15 14:02:14.402   4624 An account was successfully logged on. Logon Type: 3 (Network). Account Name: REDACTED; Source Network Address: REDACTED; Authentication Package: NTLM
2026-05-15 14:02:18.811   4672 Special privileges assigned to new logon. SubjectUserName: REDACTED; Privileges: SeBackupPrivilege, SeRestorePrivilege, SeTakeOwnershipPrivilege
2026-05-15 14:03:48.117   4688 New process. NewProcessName: C:\\Windows\\System32\\REDACTED; CommandLine: REDACTED delete shadows /all /quiet; CreatorProcessName: C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe; SubjectUserName: REDACTED
2026-05-15 14:03:52.880   4688 New process. NewProcessName: C:\\Windows\\System32\\wbem\\WMIC.exe; CommandLine: REDACTED shadowcopy delete; SubjectUserName: REDACTED
2026-05-15 14:04:19.422   4697 A service was installed. ServiceName: REDACTED; ServiceFileName: C:\\Staging\\maint.exe; StartType: Auto; ServiceAccount: LocalSystem
2026-05-15 14:04:22.107   4688 New process. NewProcessName: C:\\Staging\\maint.exe; CommandLine: maint.exe /enumerate \\\\?\\C:\\Shares; SubjectUserName: NT AUTHORITY\\SYSTEM
"""

GET_WINEVENT_SYSMON = """ProviderName: Microsoft-Windows-Sysmon

TimeCreated                Id  Process / Detail
-----------                --  ---------------
2026-05-15 14:03:48.117     1  Process Create  Image=C:\\Windows\\System32\\REDACTED  CommandLine=REDACTED delete shadows /all /quiet  ParentImage=powershell.exe  User=CORP\\REDACTED
2026-05-15 14:03:52.880     1  Process Create  Image=C:\\Windows\\System32\\wbem\\WMIC.exe  CommandLine=REDACTED shadowcopy delete  ParentImage=powershell.exe  User=CORP\\REDACTED
2026-05-15 14:04:08.221    11  FileCreate      Image=powershell.exe  TargetFilename=C:\\Staging\\maint.exe  User=CORP\\REDACTED
2026-05-15 14:04:11.882    11  FileCreate      Image=maint.exe       TargetFilename=C:\\Staging\\target-list.txt  User=NT AUTHORITY\\SYSTEM
2026-05-15 14:04:22.107     1  Process Create  Image=C:\\Staging\\maint.exe  CommandLine=maint.exe /enumerate \\\\?\\C:\\Shares  ParentImage=services.exe  User=NT AUTHORITY\\SYSTEM
2026-05-15 14:05:14.401    11  FileCreate      Image=maint.exe       TargetFilename=C:\\Shares\\Finance\\Q2-Forecast.xlsx.l0ck0kk3d  User=NT AUTHORITY\\SYSTEM
2026-05-15 14:05:14.661    11  FileCreate      Image=maint.exe       TargetFilename=C:\\Shares\\Finance\\Budget.docx.l0ck0kk3d  User=NT AUTHORITY\\SYSTEM
2026-05-15 14:05:15.144    11  FileCreate      Image=maint.exe       TargetFilename=C:\\Shares\\Finance\\Audit.pdf.l0ck0kk3d  User=NT AUTHORITY\\SYSTEM
"""

GET_PROCESS = """Handles  NPM(K)    PM(K)      WS(K)     CPU(s)     Id  ProcessName
-------  ------    -----      -----     ------     --  -----------
    411      18    25340       7212       2.41    412  explorer
    832      24    18244       5912       1.18    524  svchost
    188      11     2884       1632       0.04    448  spoolsv
    411      14    18412       6512       0.78   2104  MsMpEng
   1844      18   814200      71244     422.18   8001  maint
"""

GET_CIM_SHADOWCOPY = """(empty result)
"""

GET_SMBSESSION = """SessionId       ClientComputerName ClientUserName   NumOpens
---------       ------------------ --------------    --------
240518172401    WS-FIN-04         CORP\\REDACTED         4
240518172402    LAPTOP-NETOPS     CORP\\netops       0
"""

GET_SERVICE_FILEMAINT = """Status   Name                 DisplayName
------   ----                 -----------
Running  REDACTED      File Maintenance Helper
"""

GET_CHILDITEM_STAGING = """    Directory: C:\\Staging

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a---           5/15/2026  2:04 PM         184320 maint.exe
-a---           5/15/2026  2:04 PM           1882 target-list.txt
"""

GET_CHILDITEM_SHARES_FINANCE = """    Directory: C:\\Shares\\Finance

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a---           5/15/2026  2:05 PM          84122 Audit.pdf.l0ck0kk3d
-a---           5/15/2026  2:05 PM          51244 Budget.docx.l0ck0kk3d
-a---           5/15/2026  2:05 PM         184230 Q2-Forecast.xlsx.l0ck0kk3d
"""

WHOAMI = "corp\\administrator\n"


def _security(s, a): return GET_WINEVENT_SECURITY
def _sysmon(s, a): return GET_WINEVENT_SYSMON
def _process(s, a): return GET_PROCESS
def _shadowcopy(s, a): return GET_CIM_SHADOWCOPY
def _smbsession(s, a): return GET_SMBSESSION
def _service(s, a): return GET_SERVICE_FILEMAINT
def _childitem(s, a):
    args_lc = " ".join(a or []).lower()
    if "share" in args_lc or "finance" in args_lc:
        return GET_CHILDITEM_SHARES_FINANCE
    return GET_CHILDITEM_STAGING


def _whoami(s, a): return WHOAMI


def _winevent_router(s, a):
    # Route between REDACTED and Sysmon based on -LogName arg.
    args_lc = " ".join(a or []).lower()
    if "sysmon" in args_lc:
        return GET_WINEVENT_SYSMON
    return GET_WINEVENT_SECURITY


def _exit(s, a):
    print(); raise SystemExit


GRAMMAR = {
    "get-winevent": {"fn": _winevent_router},
    "get-eventlog": {"fn": _winevent_router},
    "get-process": {"fn": _process},
    "get-ciminstance": {"fn": _shadowcopy},
    "get-wmiobject": {"fn": _shadowcopy},
    "get-smbsession": {"fn": _smbsession},
    "get-service": {"fn": _service},
    "get-childitem": {"fn": _childitem},
    "dir": {"fn": _childitem},
    "ls": {"fn": _childitem},
    "whoami": {"fn": _whoami},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
}
