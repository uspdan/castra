# Investigation Briefing — Tier 2: Collection

Once inside FILE-01, the intruder spent three hours quietly
hoovering data before exfil. Five distinct collection techniques
fired between 14:00 and 17:00. Identify them from the Sysmon
stream, the small process-tree CSV, and the osquery hook table.

## You have

```
~/logs/sysmon.json
~/logs/process-tree.csv
~/logs/osquery-windows_hooks.json
```

## You need to answer

1. **What is the exact filename the attacker wrote the
recursive-findstr output to? (Filename only, no path.)**
   _hint: Sysmon EventID 11 (FileCreate) for a `.txt` file written
by `findstr.exe` or by its parent `REDACTED` immediately
after a findstr command._

2. **Which DLL is registered as the source of the
WH_KEYBOARD_LL hook on FILE-01? (Filename only.)**
   _hint: osquery `windows_hooks` table dump — `hook_type` column
equals 13 (WH_KEYBOARD_LL)._

3. **What file extension regex is the automated-collection
loop filtering on? (As it appears in the PowerShell
commandline — e.g. `\.(xls|csv)$`.)**
   _hint: Sysmon EventID 1, Image=powershell.exe, parent=REDACTED,
commandline contains `-match` and a regex literal._

4. **Which DLL backs the clipboard-polling hook? (Filename
only.)**
   _hint: osquery `windows_hooks` again — different `hook_type`
value (3 = WH_GETMESSAGE)._

5. **What is the absolute path of the staging archive the
attacker built before exfil? (Full path, including the
archive filename.)**
   _hint: Sysmon EventID 1 with `7z.exe` / `7za.exe` and a `-mhe=on`
argument; the output path is the last positional arg._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1005` — Data from Local System — recursive `findstr` for files containing strings like "password" / "ssn" across the share root, dumping matches to a single text artefact.
* `T1056.001` — Input Capture — Keylogging. The intruder loaded a user-mode keyboard hook via SetWindowsHookExW from a tooling DLL. An osquery snapshot captures the active WH_KEYBOARD_LL hook.
* `T1119` — Automated Collection — a small PowerShell loop walks `\\FILE-01\Finance` for any file matching a regex and copies hits into a single staging directory under `C:\ProgramData\Intel\Logs\` before compression.
* `T1115` — Clipboard Data — a second user-mode hook (WH_GETMESSAGE) tied to a different DLL polls the clipboard every 5s and appends ASCII content to a buffer file.
* `T1074.001` — Local Data Staging — the intruder rolls everything (the findstr txt, the automated-collection copies, the keylog/clipboard buffers) into a single password-protected 7z file in a hidden directory before any exfil.
