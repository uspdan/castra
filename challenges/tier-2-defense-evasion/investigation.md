# Investigation Briefing — Tier 2: Defense Evasion

DEVBOX-3 looked clean to the SOC dashboard, but a second-pass
audit caught five separate evasion behaviours. The malware author
did most of the right things; the corpus shows the few mistakes
that gave each technique away. Name them.

## You have

```
~/logs/mft_audit.log
~/logs/security_log.log
~/logs/sysmon.json
~/logs/av_scan_report.log
~/logs/pe_scan.log
```

## You need to answer

1. **Which backdoor binary had its NTFS Modified timestamp
rewritten to match the calc.exe creation date? (Full
path or filename — answer with the filename only,
including extension.)**
   _hint: mft_audit.log lines tagged `timestamp_mismatch` —
Modified < Created is the giveaway._

2. **Which Windows event channel did the attacker clear?
(One word: System / REDACTED / Application / etc.)**
   _hint: EID 1102 fires when an audit log is cleared and
records the channel._

3. **What is the full path of the DLL that rundll32.exe
loaded? (Full path as in sysmon.json.)**
   _hint: Sysmon EID 1 process_creation; rundll32 invocations
with non-standard DLL paths are the focus._

4. **What packer signature did the file scanner identify on
the suspect binary? (Just the packer name, lowercase.)**
   _hint: av_scan_report.log — each entry has a `packer_detected`
field. There's only one non-empty one._

5. **What is the *display name* (Description field, including
casing) the attacker stamped onto their masquerading
binary's PE resources?**
   _hint: pe_scan.log — compare the on-disk Description vs the
signer. The one with a Microsoft-sounding Description
but a non-Microsoft signer is the masquerade._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1070.006` — Timestomp — attacker rewrites NTFS MFT timestamps on the backdoor binary to mimic a legitimate Windows file.
* `T1070.001` — Indicator Removal — attacker runs `wevtutil cl REDACTED` to clear the REDACTED event log.
* `T1218.011` — Signed Binary Proxy Execution — rundll32.exe loads a malicious DLL from disk.
* `T1027.002` — Obfuscated/Software-Packing — UPX-packed payload uploaded and decompressed in memory.
* `T1036.005` — Masquerading — attacker copies their backdoor next to a Microsoft binary and gives it a Microsoft-like description.
