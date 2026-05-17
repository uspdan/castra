# Investigation Briefing — WS-FIN-04 (Live)

`WS-FIN-04` (Windows 11 Enterprise, domain-joined `corp.local`)
belongs to a finance user who reported "my Word doc was being
weird this morning". EDR fired a low-confidence alert on
`schtasks.exe /create ... /ru SYSTEM`. Confirm the chain.

## Connect

```sh
connect ws-fin-04
```

Any user/password lands you at `PS C:\Users\REDACTED>`.

## You have

A live PowerShell session on `WS-FIN-04` via `connect`. Cmdlets
case-insensitive. Pipes (`| include`, `| match`, `| exclude`,
`| count`) work everywhere.

## You need to answer

```
Get-WinEvent                    # synthetic — Sysmon Operational view
Get-ScheduledTask
Get-ScheduledTask -TaskName <name>
Get-Process
Get-NetTCPConnection
Get-ChildItem                   # also: dir / ls
Get-LocalUser
whoami
```

1. Filename of the macro-laden document the user opened.
2. Full URL the decoded `-EncodedCommand` PowerShell pulls from.
3. Name of the persistence scheduled task.
4. C2 destination IP of the persistence binary.
5. Absolute Windows path of the dropped binary.

## Decoding the EncodedCommand

The `-EncodedCommand` argument is normally PowerShell base64
(UTF-16LE). For the sake of this exercise the staged blob is
straight UTF-8 base64 — so `printf '<blob>' | base64 -d` from any
shell decodes it cleanly.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
