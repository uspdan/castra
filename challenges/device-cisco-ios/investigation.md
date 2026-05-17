# Investigation Briefing — Device Forensics: Cisco IOS Compromise

BR-EDGE-01 (Cisco 2911, IOS 15.7) was compromised overnight.
You have the post-incident running-config dump, terminal
session log, syslog excerpt, and SNMP state. Five distinct
bits of attacker tradecraft are visible. Find them.

## You have

```
~/logs/running-config.txt
~/logs/approved-users.txt
~/logs/show-users.txt
~/logs/show-snmp.txt
~/logs/syslog.txt
```

## You need to answer

1. **What is the username of the rogue privilege-level-15 local
account the attacker added? (Lowercase username only.)**
   _hint: running-config.txt — look for `username ... privilege 15`
entries and compare to /home/hunter/logs/approved-users.txt._

2. **What is the SNMP community string configured with RW
(read-write) access? (Exact string, case-sensitive.)**
   _hint: running-config.txt and show-snmp.txt both name it. Look
for `snmp-server community ... RW`._

3. **What is the destination IP of the unauthorised GRE tunnel
the attacker created on Tunnel0? (Format x.x.x.x.)**
   _hint: running-config.txt — `interface Tunnel0` block, look at
`tunnel destination`._

4. **Which ACL number was modified to permit outbound traffic
to the attacker's C2 prefix? (Number only, e.g. 103.)**
   _hint: running-config.txt — look for `access-list NNN permit ...
198.51.100.0 0.0.0.255` (the C2 /24 the GRE points into)._

5. **From which source IP did the attacker authenticate to the
vty over SSH for the privileged config changes? (Format
x.x.x.x.)**
   _hint: syslog.txt — multiple `%SEC_LOGIN-5-LOGIN_SUCCESS` lines
from the same external IP into vty 0; show-users.txt
confirms the live session._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1078` — Valid Accounts — a rogue privilege-15 local user (not on the approved roster) appears in running-config.
* `T1078.001` — Default / weak credentials — an SNMP community string with RW (read-write) access set to a guessable value.
* `T1133` — External Remote Services — a GRE tunnel interface points at an attacker-controlled tunnel endpoint outside the org IP space.
* `T1562.004` — Impair Defenses — Disable or Modify System Firewall. The outbound ACL was edited to permit traffic to the attacker's C2 prefix that would otherwise have been dropped by the default deny-any.
* `T1021.004` — Remote Services — SSH. The attacker authenticated to vty 0 4 from a single source IP across the change window.
