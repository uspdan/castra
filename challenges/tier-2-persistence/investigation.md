# Investigation Briefing — Tier 2: Persistence

EDR caught a single foothold on WORK02 but the attacker had a
window of about an hour before the host was isolated. Five
separate persistence mechanisms were planted in that window —
pick them apart from the logs.

## You have

```
~/logs/registry_audit.log
~/logs/scheduled_tasks.log
~/logs/service_install.log
~/logs/wmi_subscriptions.log
~/logs/bits_jobs.log
```

## You need to answer

1. **What registry value name did the attacker create under the
Run key? (Just the value name, exact case.)**
   _hint: registry_audit.log — RegistryValueSet events with
TargetObject ending in `\Run\<name>`._

2. **What is the exact name of the scheduled task the attacker
created? (As shown in scheduled_tasks.log.)**
   _hint: Filter to action=create._

3. **What is the service name (not the display name) the
attacker installed? (As shown in service_install.log.)**
   _hint: Look for an install event with binPath pointing at a
non-standard location like C:\ProgramData\…_

4. **What is the name of the WMI EventConsumer the attacker
registered? (As stored in WMI repository.)**
   _hint: wmi_subscriptions.log — look for the consumer record paired
with a __EventFilter and __FilterToConsumerBinding._

5. **What is the BITS job display name (DisplayName field)
the attacker created? (Exact string.)**
   _hint: bits_jobs.log — focus on the entry whose RemoteName host
doesn't match any approved Microsoft / corp domain._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1547.001` — Registry Run Keys — backdoor binary registered under HKCU\Software\Microsoft\Windows\CurrentVersion\Run.
* `T1053.005` — Scheduled Task — daily task that re-launches the backdoor at 03:30 if killed.
* `T1543.003` — Windows Service — a SYSTEM service that auto-starts at boot and runs the backdoor binary.
* `T1546.003` — Event Triggered Execution — WMI subscription that fires on a process-create matching REDACTED.
* `T1197` — BITS Jobs — long-lived BITS download job pointing at attacker infrastructure that re-fetches the backdoor on a schedule.
