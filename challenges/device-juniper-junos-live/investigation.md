# Investigation Briefing — srx-perim-01 (Live)

`srx-perim-01` (Juniper SRX 340, Junos 21.2R3-S2.5) is your branch
firewall. An unscheduled commit landed at 03:14:22 UTC under the
`netops` account from an IP that doesn't belong to corp. Reconstruct
exactly what changed.

## Connect

```sh
connect srx-perim-01
```

Any user/password works (NOC). You'll land at the Junos
operational prompt `admin@srx-perim-01>`.

## You have

A live Junos CLI on `srx-perim-01` via `connect`.

## You need to answer

```
show version                                # software / model
show system users                           # current sessions
show configuration | display set            # full config in set form
show configuration system login             # users + classes
show security policies                      # SRX rulebase
show system commit                          # commit history with sequence
show log messages                           # syslog
```

Pipes: `| match <re>`, `| display set`, `| include <re>`, `| exclude`, `| begin`, `| count`.

1. Username of the rogue super-user account added to `/system/login`.
2. Source IP from which the attacker SSHed in.
3. Sequence number of the malicious commit.
4. Name of the security policy widened toward the attacker's prefix.
5. CIDR of the `attacker-c2` global address-book entry.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
