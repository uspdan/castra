# Investigation Briefing — EXCH-01 (Live)

`EXCH-01` (Microsoft Exchange Server 2019 CU12, build 15.2.1118.7
— vulnerable to **ProxyShell**, CVE-2021-34473 / CVE-2021-34523 /
CVE-2021-31207, never patched). DLP just flagged a 50 MB .pst
download from a non-corp IP. Confirm.

## Connect

```sh
connect exch-01
```

Any user/password lands you at the Exchange Management Shell.

## You have

A live EMS session on `EXCH-01.corp.local` via `connect`.

## You need to answer

```
Get-ExchangeServer
Get-Mailbox
Get-MailboxExportRequest
Get-MailboxExportRequest -Identity <name>
Get-RoleGroupMember "Organization Management"
Get-ChildItem C:\inetpub\wwwroot\aspnet_client\system_web
Get-IISAccessLog               # synthetic — IIS combined log
Get-WinEvent
```

1. Unauth URL path the attacker hit for the AutoDiscover SSRF.
2. Filename of the .aspx webshell under aspnet_client/system_web.
3. Mailbox alias of the highest-priority export target.
4. Full FilePath the CFO mailbox was exported to.
5. Source IP of the exploit traffic.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
