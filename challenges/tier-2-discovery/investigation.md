# Investigation Briefing — Tier 2: Discovery

The attacker landed quietly on SRVR-04 and spent twenty minutes
mapping the environment before doing anything else. Reconstruct
the discovery chain from a single Sysmon JSONL stream.

## You have

```
~/logs/sysmon.json
~/logs/procs.txt
```

## You need to answer

1. **Which built-in Windows binary did the attacker use to list
the domain controllers? (Just the filename, e.g. foo.exe.)**
   _hint: Look for arguments like /dclist._

2. **What file extension was the attacker hunting for in the
recursive find? (Format: .ext, including the dot.)**
   _hint: A dir /s or where invocation with a *.* pattern._

3. **What AD group did the attacker enumerate for membership?
(Exact name as passed to net group, no quotes.)**
   _hint: net group has the group name as its first argument._

4. **Which AV/EDR product name appeared in the tasklist output
the attacker dumped to disk? (Vendor product name as it
shows in Image Name — lowercase, e.g. `REDACTED`.)**
   _hint: Sysmon FileCreate of a .txt artefact; inside, look for
any process from a known EDR vendor._

5. **Which remote hostname did the attacker enumerate shares on
immediately before moving sideways? (Hostname only, no UNC,
uppercase.)**
   _hint: net view \\HOSTNAME /all._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1018` — Remote System Discovery — net view + nltest /dclist to map hosts and domain controllers.
* `T1083` — File and Directory Discovery — recursive search for sensitive file extensions.
* `T1087.002` — Domain Account Discovery — net group "REDACTED" enumeration.
* `T1057` — Process Discovery — tasklist /v looking for AV/EDR processes.
* `T1135` — Network Share Discovery — net view \\hostname /all to enumerate shares.
