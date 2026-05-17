# Investigation Briefing — BR-EDGE-01 (Live)

`BR-EDGE-01` (Cisco 2911 ISR, IOS 15.7(3)M5) has been kicking off
unusual traffic since the early hours. The device is still up.
Your NOC has read-only access; the on-call NOC engineer left you
the **enable secret** so you can run privileged-mode show
commands.

## Connect

From this shell:

```sh
connect br-edge-01
```

NOC read-only credentials (any username/password works for the
sake of the exercise — pretend it's `noc-readonly / <ldap-creds>`).
Once at the user prompt, type `enable` and use the password from
the NOC's break-glass envelope:

```
enable password:  n0c-l3v3l-15
```

## You have

* A live Cisco IOS CLI on `BR-EDGE-01` (via `connect`).
* `~/approved-users.txt` — the NOC's authorised local-user roster
  (last reviewed 2026-04-01).

## You need to answer

Use whatever IOS commands you'd normally reach for — `show
running-config`, `show users`, `show snmp`, `show logging`, `show
access-lists`, `show history`. Pipes work (`| include`, `|
exclude`, `| section`, `| begin`, `| count`).

1. What is the username of the rogue privilege-level-15 local
   account the attacker added?
2. What is the SNMP community string configured with RW access?
3. What is the destination IP of the unauthorised GRE tunnel on
   `Tunnel0`?
4. Which ACL number was modified to permit outbound traffic to
   the attacker's C2 prefix?
5. From which source IP did the attacker authenticate to the
   vty over SSH?

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## Hints baked into the device

* `show users` — see who else is on the box right now.
* `show history` — the previous user's per-line history buffer
  is intact; the attacker's command trail is still there.
* `show running-config | section interface Tunnel0` — block-mode
  pipe focuses on a specific interface.
* `show running-config | include snmp` — line-mode pipe pulls
  every SNMP-related line.
