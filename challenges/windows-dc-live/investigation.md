# Investigation Briefing — DC01.corp.local (Live)

`DC01.corp.local` (Windows Server 2022, AD DS) is your forest
root DC. Detection flagged unusual replication traffic from a
non-DC IP yesterday afternoon, plus an account-creation event
nobody on the AD team owns up to. Walk the live PowerShell session
and reconstruct the chain.

## Connect

```sh
connect dc01
```

Any user/password lands you at `PS C:\Users\Administrator>`.

## You have

A live PowerShell session on `DC01.corp.local` via `connect`. The
shell accepts case-insensitive cmdlet names and supports the
engine's pipe operators (`| include` / `| match` / `| exclude` /
`| begin` / `| count`) as a stand-in for `Where-Object` /
`Measure-Object` filtering.

## You need to answer

Most useful cmdlets:

```
Get-ADUser -Filter * -Properties ServicePrincipalName   # all AD users + SPNs
Get-ADGroupMember "REDACTED"                        # DA roster
Get-ADComputer -Filter *                                 # domain-joined computers
Get-ADObject -SearchBase "CN=AdminSDHolder,CN=System,DC=corp,DC=local" -Properties ntREDACTEDDescriptor
Get-WinEvent -LogName REDACTED                           # security event log
Get-LocalUser                                            # local SAM accounts
whoami /priv
```

1. Service account whose SPN is the Kerberoasting target.
2. The exact SPN string the attacker requested tickets for.
3. SamAccountName of the rogue REDACTED member.
4. Source workstation IPv4 from which `REDACTED` first authenticated.
5. Windows event ID that documents the DCSync replication access.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
