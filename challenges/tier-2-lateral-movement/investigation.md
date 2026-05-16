# Investigation Briefing — Tier 2: Lateral Movement

An attacker is moving inside a corporate Windows network. You have
Sysmon ProcessCreate events, security event logs, and SMB session
logs from five hosts. Reconstruct the lateral-movement chain and
identify the technique used at each hop.

## You have

```
~/logs/WORK01_sysmon.json
~/logs/FILE01_security.log
~/logs/FILE01_sysmon.json
~/logs/DC01_smb_session.log
~/logs/DC02_sysmon.json
~/logs/AUDIT01_sysmon.json
```

## You need to answer

1. **Which protocol did the attacker use to move from WORK01 to FILE01?
(One word, lowercase.)**
   _hint: security.log on FILE01 — look for EID 4624 with LogonType=10._

2. **What hidden SMB share name did the attacker access on DC01?
(Format: <share name>, e.g. `C$`.)**
   _hint: smb_session.log on DC01 — look for an unusual access from
FILE01's machine account._

3. **Which Microsoft binary (lowercase, full filename) did the
attacker invoke locally to spawn the remote process on DC02?**
   _hint: Sysmon on the calling host shows the binary in
`CommandLine`. Think classic WMI dual-use tool._

4. **What is the name of the scheduled task the attacker created
on AUDIT01? (Exact string, as logged.)**
   _hint: Sysmon EID 1 / schtasks.exe with the /tn argument._

5. **What DCOM ProgID did the attacker abuse for the final hop?
(Lowercase, including the dot.)**
   _hint: Sysmon shows the powershell.exe call invoking
`[Activator]::CreateInstance(...)` on a specific ProgID._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1021.001` — Remote Desktop Protocol — attacker reuses a stolen credential to RDP from WORK01 into FILE01. REDACTED log shows EID 4624 logon type 10.
* `T1021.002` — SMB Admin Shares — attacker uses net use \\DC01\C$ to access the domain controller's hidden admin share.
* `T1047` — WMI Remote Execution — attacker uses wmic /node:DC02 process call create REDACTED to launch a process on a second DC.
* `T1053.005` — Scheduled Task / Job (At) — attacker uses schtasks /create /s AUDIT01 /tn ... to register a remote task on AUDIT01 that runs as SYSTEM at next boot.
* `T1021.003` — Distributed Component Object Model — attacker pivots from AUDIT01 back to FILE01 using REDACTED DCOM instantiation.
