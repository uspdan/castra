# Investigation Briefing — Tier 2: Impact

A ransomware-style operator went loud on five hosts in a single
hour. Identify the impact technique used on each affected
system from the available evidence.

## You have

```
~/logs/filesystem_changes.log
~/logs/sysmon.json
~/logs/wipe_audit.log
~/logs/deletion_audit.log
~/logs/ad_changes.log
```

## You need to answer

1. **What file extension is appended to encrypted files on
host FILE-01? (Format: .ext, including the dot.)**
   _hint: filesystem_changes.log — file creation events._

2. **Which Windows built-in did the attacker use to delete
shadow copies on host BACKUP-2? (Filename, lowercase.)**
   _hint: sysmon.json process_creation, command line includes
`delete shadows`._

3. **What database directory on DB-3 was overwritten with
random data? (Full path.)**
   _hint: wipe_audit.log — look for the largest write of pattern
`random` to a path under a database product folder._

4. **How many files were deleted from FINANCE-9 in the bulk
delete operation? (Just the integer.)**
   _hint: deletion_audit.log — single user/process responsible
for a count._

5. **How many admin accounts were disabled by the attacker
on AD-1? (Just the integer.)**
   _hint: ad_changes.log — EID 4725 (account disabled) events
with the same actor._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1486` — Data Encrypted for Impact — every file under /data is replaced with REDACTED extensions and a ransom note dropped.
* `T1490` — Inhibit System Recovery — vssadmin delete shadows /all /quiet.
* `T1561.001` — Disk Content Wipe — selective overwriting of high-value database directories on host DB-3.
* `T1485` — Data Destruction — bulk delete of monthly accounting CSVs on host FINANCE-9.
* `T1531` — Account Access Removal — attacker disables 12 admin accounts to hamper response on host AD-1.
