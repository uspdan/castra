# Investigation Briefing — mkt-rb750 (Live)

`mkt-rb750` (MikroTik RB750Gr3, RouterOS 7.10.1) is a branch
edge that hadn't been patched against the CVE-2018-14847 Winbox
auth-bypass. Threat-intel just flagged its WAN IP in an
attacker-domain DNS query. Confirm.

## Connect

```sh
connect mkt-rb750
```

Any user/password (NOC). You'll land at MikroTik's
`[admin@mkt-rb750] > ` prompt. Commands are slash-prefixed
hierarchies — every leaf takes a verb like `print`.

## You have

A live RouterOS CLI on `mkt-rb750` via `connect`.

## You need to answer

```
/system identity print
/system resource print
/user print
/system scheduler print
/system script print
/ip firewall nat print
/ip firewall filter print
/log print
```

1. Name of the unauthorised scheduled job.
2. Local user that owns the malicious scheduler script.
3. C2 domain the script's `/tool fetch` calls out to.
4. Comment (`;;;` annotation) on the rogue NAT rule.
5. Internal IP the rogue NAT rule forwards to on TCP/22.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
