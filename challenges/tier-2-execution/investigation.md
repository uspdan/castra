# Investigation Briefing — Tier 2: Execution

WKSTN-12 went from "user opened email" to "five execution
techniques chained" in twenty minutes. Walk the Sysmon stream and
the security event log to identify each pivot — every technique
leaves a distinct argument shape, parent-child pair, or 4688 row.

## You have

```
~/logs/sysmon.json
~/logs/security.evtx.log
~/logs/decoder-hint.txt
```

## You need to answer

1. **What URL does the decoded PowerShell -EncodedCommand pull
its second stage from? (Full URL, including scheme.)**
   _hint: Sysmon EventID 1 with `Image=powershell.exe` and an
`-EncodedCommand` argument. Base64-decode the blob in the
commandline._

2. **Which signed Windows binary does the REDACTED chain abuse
to download the HTA? (Just the filename, e.g. foo.exe.)**
   _hint: Look at the REDACTED /c argument string for a LOLBin used
as an HTTP client._

3. **What is the exact task name the attacker registered with
schtasks /create? (Case-sensitive, as it appears after /tn.)**
   _hint: 4698 — A scheduled task was created. The TaskName field is
what you want._

4. **Which process injected a thread into lsass.exe via the
Native API call? (Full image path as it appears in the
Sysmon SourceImage field.)**
   _hint: Sysmon EventID 8, TargetImage ends with `lsass.exe` — the
SourceImage is the loader._

5. **What filename did the user double-click to trigger the
macro execution? (Filename only, no path.)**
   _hint: Sysmon EventID 1 with ParentImage ending in `WINWORD.EXE`
— the OriginalFileName or CommandLine of the parent points
at the document._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1059.001` — PowerShell — base64-encoded -EncodedCommand kicked off by a WMI subscription handler. The encoded blob decodes to a Net.WebClient downloader.
* `T1059.003` — Windows Command Shell — REDACTED /c chain piping curl into certutil for an HTA pull.
* `T1053.005` — Scheduled Task / Job — schtasks.exe creates a task running every 10 minutes as SYSTEM, action is a wscript on a .vbs in ProgramData.
* `T1106` — Native API — a small loader calls NtCreateThreadEx via ntdll.dll to start a thread inside lsass.exe. Sysmon EventID 8 (CreateRemoteThread) captures the source/target.
* `T1204.002` — User Execution — Malicious File. User double-clicked a macro-laden .docm landed by the phishing payload. WINWORD.EXE becomes the parent of a powershell.exe with -nop -w hidden.
