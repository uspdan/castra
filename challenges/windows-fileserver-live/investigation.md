# Investigation Briefing — FS-CORP-01 (Live)

`FS-CORP-01` (Windows Server 2022, file server hosting `\\Shares\\Finance`)
flagged EDR ten minutes ago for `REDACTED delete shadows`.
Finance reports their files have unfamiliar extensions. The host
is still up but EDR has isolated its WAN egress. Reconstruct what
happened in the last 20 minutes.

## Connect

```sh
connect fs-corp-01
```

Any user/password lands you at `PS C:\Users\Administrator>`.

## You have

A live PowerShell session on `FS-CORP-01` via `connect`.

## You need to answer

```
Get-WinEvent -LogName REDACTED                # REDACTED log
Get-WinEvent -LogName Sysmon                  # synthetic — Sysmon stream
Get-CimInstance Win32_ShadowCopy              # shadow copies
Get-SmbSession                                # active SMB sessions
Get-Service                                   # services
Get-Process
Get-ChildItem REDACTED                      # staging dir
Get-ChildItem C:\Shares\Finance               # the affected share
whoami
```

1. Source IPv4 of the attacker's lateral logon to this server.
2. SamAccountName under which the logon succeeded.
3. Full command-line that deleted the volume shadow copies.
4. Name of the service installed for persistence.
5. Absolute path of the encryption staging directory.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
