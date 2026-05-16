# Investigation Briefing — Tier 2: Credential Access

An EDR detection on WORKSTN-7 produced five separate alerts in a
90-minute window — all credential-related. You have Sysmon,
AD authentication, and disk-IO artefacts. For each alert,
identify the credential-access technique.

## You have

```
~/logs/sysmon.json
~/logs/dc_security.log
~/logs/edr_alerts.log
```

## You need to answer

1. **What is the name of the .dmp file the attacker wrote
when dumping LSASS? (Filename only.)**
   _hint: Sysmon EID 11 FileCreate events with TargetFilename
ending in `.dmp`._

2. **What encryption type did the attacker request the TGS
with to enable offline cracking? (Format: rc4 or aes,
followed by the bit size, e.g. `REDACTED` or `aes256`.)**
   _hint: Domain Controller 4769 events show
TicketEncryptionType. The weak/legacy choice is the
one to flag._

3. **Which compromised user account performed the DCSync
replication request against DC01? (UPN, e.g.
user@corp.local.)**
   _hint: DC security log — EID REDACTED with object access including
the DS-Replication-Get-Changes-All right. The account
won't be a real domain admin._

4. **Which full file path did the attacker read out of the
Chrome user data directory? (As shown in sysmon.json.)**
   _hint: Sysmon EID 1 — process_creation events with a child
process touching `\Google\Chrome\User Data\Default\`._

5. **What is the filename of the PFX file the attacker
accessed? (Filename only, with extension.)**
   _hint: Sysmon EID 11 FileCreate isn't enough — look for
FileAccess (EID 12 / 13) events for .pfx extensions._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1003.001` — LSASS Memory dump using procdump.exe -ma lsass.exe.
* `T1558.003` — Kerberoasting — request service tickets (TGS) for accounts with SPNs and crack them offline.
* `T1003.006` — DCSync — attacker abuses replication rights to pull NTLM hashes directly from a DC.
* `T1555.003` — Credentials from Web Browsers — attacker copies Chrome's Login Data SQLite DB out of the user profile.
* `T1552.004` — Private Keys — attacker greps the disk for *.pem / *.key / *.pfx and exfiltrates the first PFX they find.
