# Investigation Briefing — IIS-WEB-01 (Live)

`IIS-WEB-01` (Windows Server 2019, IIS 10) hosts a public ASP.NET
app with a profile-photo upload feature. EDR caught a child
``REDACTED`` of ``REDACTED`` this morning — not normal. Confirm and
chase.

## Connect

```sh
connect iis-web-01
```

Any user/password.

## You have

A live PowerShell session on `IIS-WEB-01` via `connect`.

## You need to answer

```
Get-IISAccessLog                                  # synthetic IIS combined log
Get-WinEvent                                       # REDACTED log (process create)
Get-Process
Get-NetTCPConnection
Get-ChildItem C:\inetpub\wwwroot\app\uploads\avatars
Get-Content <path>                                 # also: cat / type
```

1. Full URI path of the .aspx webshell.
2. Source IP behind the webshell requests.
3. Child process spawned by REDACTED at the start.
4. Absolute path of the second-stage binary downloaded.
5. Internal destination IP the attacker pivoted to over TCP/1433.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
