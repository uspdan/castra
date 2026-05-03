# Off-hours PowerShell triage

The on-call SOC dumped six `process_creation` events from the EDR
overnight. Two of them are unauthorised — interactive PowerShell
launched by a user account when the user is supposed to be off-shift.
The rest is service noise.

## Event log shape

Each entry is a JSON object with these fields:

| Field | Meaning |
|---|---|
| `EventID` | Windows EventID; `4688` = process creation, `4624` = logon |
| `Image` | Full path to the executed image |
| `User` | Account the process ran as |
| `CommandLine` | Recorded command line (best-effort) |

## Your task

Write a Sigma rule that, when replayed against the six events,
matches **exactly** the two unauthorised launches and nothing else.

Submit the rule as the flag. The grader compiles it with pysigma and
replays it through an in-process matcher.

## Constraints

* The rule must declare `logsource.product: windows` and
  `logsource.category: process_creation`. Anything else is rejected.
* Anchored field-equality + the standard string modifiers
  (`contains`, `startswith`, `endswith`) are supported. Exotic
  modifiers (`base64offset`, `cidr`) are not.
* Submissions are size-capped at 64 KiB.
