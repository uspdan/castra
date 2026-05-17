# Investigation Briefing — Tier 2: Privilege Escalation

Four hosts in your fleet went from low-privilege user to root /
SYSTEM in the same hour. Each climbed a different ladder. Walk
the auditd and Sysmon evidence, identify the technique, and pull
out the one detail that ties the technique to the host.

## You have

```
~/logs/auditd.log
~/logs/sysmon.json
~/logs/windows-security.log
```

## You need to answer

1. **What is the full path of the unauthorised setuid binary
the attacker dropped on LNX-WEB-01? (Absolute path.)**
   _hint: auditd SYSCALL type=PATH with mode=04... — chmod
4755 against a binary outside the normal setuid set._

2. **What is the filename of the DLL injected into MsiExec.exe
on WIN-FIN-04? (Filename only, no path.)**
   _hint: Sysmon EventID 7 (Image loaded) against `MsiExec.exe`
for an image outside `C:\Windows\System32`, immediately
followed by EventID 8 with TargetImage=MsiExec.exe._

3. **Which non-System SID was the parent logon for the new
REDACTED that suddenly held SeTcbPrivilege on WIN-FIN-09?
(SID format S-1-5-21-...-XXXX.)**
   _hint: REDACTED 4672 — SeTcbPrivilege granted to REDACTED; trace
the SubjectLogonId back to its 4624 row for the SID._

4. **Which dormant local account did the attacker reactivate
on LNX-WEB-02 to climb to root? (Username only.)**
   _hint: auditd USER_CHAUTHTOK followed by a successful sshd
accept for that user from 127.0.0.1._

5. **What was the exact registry value written under the
ms-settings shell-open hijack key on WIN-FIN-04? (The
Data field of the (Default) value, verbatim.)**
   _hint: Sysmon EventID 13 (RegistryValueSet) — TargetObject ends
with `\ms-settings\shell\open\command\(Default)`._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1548.001` — Abuse Elevation Control Mechanism — Setuid and Setgid. An orphan setuid copy of /bin/bash dropped under /var/tmp by the web user and re-executed as root.
* `T1055.001` — Process Injection — DLL Injection. On WIN-FIN-04 a sideloaded DLL is mapped into the elevated MsiExec.exe service process, then a remote thread starts inside it.
* `T1134.001` — Access Token Manipulation — Token Impersonation/Theft. On WIN-FIN-09 the attacker uses a tooling process to duplicate a SYSTEM token and re-launch REDACTED with it. 4672 (special privileges) fires for the new process under a non-admin logon ID.
* `T1078.003` — Valid Accounts — Local Accounts. On LNX-WEB-02 an unused local service account (`REDACTED`) is reactivated via a passwd change by root through a pre-existing webshell, then used to ssh in over loopback with sudo NOPASSWD on `tar`.
* `T1548.002` — Abuse Elevation Control Mechanism — Bypass UAC. On WIN-FIN-04 the attacker uses the fodhelper.exe shell-open hijack to auto-elevate a REDACTED without prompting. A registry write under HKCU\Software\Classes\ms-settings\shell\open\command sets the payload.
