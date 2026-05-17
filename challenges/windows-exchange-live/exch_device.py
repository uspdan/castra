"""Exchange Server 2019 CU12 device data + grammar for EXCH-01.

Backdrop: classic ProxyShell exploit chain
(CVE-2021-34473 + CVE-2021-34523 + CVE-2021-31207). Unauthenticated
attacker hit ``REDACTED?@<DOMAIN>/...`` to
reach the Exchange PowerShell endpoint via the AutoDiscover SSRF
+ PowerShell remote-shell elevation, then ran
``New-MailboxExportRequest`` to drop an .aspx webshell into the
``/aspnet_client/system_web/`` directory, plus exfil'd a target
mailbox to a PST under the same path.

This sim wraps the Exchange Management Shell (EMS) cmdlets plus
the IIS access-log surface that's the canonical ProxyShell
forensics signal.
"""

from __future__ import annotations

import sys

HOSTNAME = "EXCH-01"

BANNER = """Microsoft Windows [Version 10.0.17763.4974]
(c) Microsoft Corporation. All rights reserved.

The Exchange Management Shell session has been initialized.

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "User name: "
AUTH_PASSWORD_PROMPT = "Password: "

PROMPT_SUFFIXES = {"user": "> "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"[PS] C:\\Windows\\system32{suffix}"


GET_EXCH_VERSION = """AdminDisplayVersion : 15.2 (Build 1118.7)
ServerRole          : Mailbox, ClientAccess
Edition             : Enterprise
Site                : Default-First-Site-Name
"""

GET_MAILBOX = """Name              Alias       ServerName   ProhibitSendQuota
----              -----       ----------   -----------------
Administrator     admin       EXCH-01      unlimited
J Doe             REDACTED        EXCH-01      50 GB (53687091200 B)
CFO Office        cfo         EXCH-01      50 GB
HR Mailbox        hr          EXCH-01      50 GB
SecOps Distro     secops      EXCH-01      50 GB
"""

GET_MAILBOX_EXPORT_REQUEST = """Name                               SourceAlias  Status     FilePath
----                               -----------  ------     --------
MailboxExport-fb22                  cfo          Completed  \\\\EXCH-01\\c$\\inetpub\\wwwroot\\aspnet_client\\system_web\\cfo-export.pst
MailboxExport-fb23                  hr           Completed  \\\\EXCH-01\\c$\\inetpub\\wwwroot\\aspnet_client\\system_web\\hr-export.pst
"""

GET_MAILBOX_EXPORT_REQUEST_DETAIL = """Identity            : EXCH01\\MailboxExport-fb22
RequestQueue        : Mailbox Database 1241914841
Status              : Completed
SourceAlias         : cfo
FilePath            : \\\\EXCH-01\\c$\\inetpub\\wwwroot\\aspnet_client\\system_web\\cfo-export.pst
WhenCreated         : 2026-05-17 09:11:34
RequestStyle        : Intra-organizational
Suspended           : False
RequestedBy         : NT AUTHORITY\\SYSTEM
"""

GET_ROLE_GROUP_MEMBER_ORGMGMT = """Name              SamAccountName
----              --------------
Administrator     administrator
exch-mgmt         exch-mgmt
"""

GET_IIS_ACCESS_LOG = """#Software: Microsoft Internet Information Services 10.0
#Fields: date time c-ip cs-method cs-uri-stem cs-uri-query sc-status cs(User-Agent)
2026-05-17 09:08:11 REDACTED GET  REDACTED   "?@example.com/Powershell&Email=autodiscover/autodiscover.json%3F@example.com" 200 "python-requests/2.31.0"
2026-05-17 09:08:14 REDACTED POST REDACTED   "?@example.com/Powershell&Email=autodiscover/autodiscover.json%3F@example.com" 200 "python-requests/2.31.0"
2026-05-17 09:09:01 REDACTED POST /Powershell                       "?X-Rps-CAT=<long-base64>"                                  200 "python-requests/2.31.0"
2026-05-17 09:11:34 REDACTED POST /Powershell                       "?X-Rps-CAT=<long-base64>"                                  200 "python-requests/2.31.0"
2026-05-17 09:11:55 REDACTED GET  /aspnet_client/system_web/REDACTED  "?cmd=whoami"                                              200 "curl/8.4"
2026-05-17 09:12:08 REDACTED GET  /aspnet_client/system_web/REDACTED  "?cmd=Get-MailboxExportRequest"                            200 "curl/8.4"
2026-05-17 09:14:11 REDACTED GET  /aspnet_client/system_web/cfo-export.pst ""                                                 200 "wget/1.21"
"""

GET_CHILDITEM_ASPNET_CLIENT = """    Directory: C:\\inetpub\\wwwroot\\aspnet_client\\system_web

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a---           5/17/2026  9:11 AM          412   REDACTED
-a---           5/17/2026  9:11 AM       8412044  cfo-export.pst
-a---           5/17/2026  9:11 AM       4218012  hr-export.pst
"""

GET_WINEVENT_SECURITY = """ProviderName: Microsoft-Windows-REDACTED-Auditing

TimeCreated                Id  Message
-----------                --  -------
2026-05-17 09:08:14.122   4688 New process. NewProcessName: C:\\Windows\\System32\\REDACTED; CommandLine: REDACTED -ap "MSExchangeAutodiscoverAppPool" -v "v4.0"; SubjectUserName: NT AUTHORITY\\NetworkService
2026-05-17 09:09:01.882   4624 An account was successfully logged on. Logon Type: 8 (NetworkClearText). Account Name: SYSTEM (via Exchange PowerShell remoting); Source: 127.0.0.1
2026-05-17 09:11:34.402   4688 New process. NewProcessName: C:\\Program Files\\Microsoft\\Exchange Server\\V15\\Bin\\ExSetup.exe; CommandLine: ExSetup.exe ... New-MailboxExportRequest -Mailbox cfo -FilePath \\\\EXCH-01\\c$\\inetpub\\wwwroot\\aspnet_client\\system_web\\cfo-export.pst
"""


def _exch_version(s, a): return GET_EXCH_VERSION
def _mailbox(s, a): return GET_MAILBOX
def _mailbox_export(s, a):
    args_lc = " ".join(a or []).lower()
    if "-identity" in args_lc and "fb22" in args_lc:
        return GET_MAILBOX_EXPORT_REQUEST_DETAIL
    return GET_MAILBOX_EXPORT_REQUEST


def _role_group_member(s, a): return GET_ROLE_GROUP_MEMBER_ORGMGMT
def _iis_log(s, a): return GET_IIS_ACCESS_LOG
def _childitem(s, a): return GET_CHILDITEM_ASPNET_CLIENT
def _winevent(s, a): return GET_WINEVENT_SECURITY


def _exit(s, a):
    print(); raise SystemExit


GRAMMAR = {
    "get-exchangeserver": {"fn": _exch_version},
    "get-mailbox": {"fn": _mailbox},
    "get-mailboxexportrequest": {"fn": _mailbox_export},
    "get-rolegroupmember": {"fn": _role_group_member},
    "get-childitem": {"fn": _childitem},
    "dir": {"fn": _childitem},
    "ls": {"fn": _childitem},
    "get-iisaccesslog": {"fn": _iis_log},  # synthetic
    "get-winevent": {"fn": _winevent},
    "get-eventlog": {"fn": _winevent},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
}
