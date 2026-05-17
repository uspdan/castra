# Investigation Briefing — FW-DC-01 (Live)

`FW-DC-01` (Palo Alto PA-3220, PAN-OS 10.2) is the DC perimeter
firewall and GlobalProtect concentrator. Last night a contractor
account logged in from an IP that had 237 failed auth attempts
ahead of it in a tight window, then jumped to a Domain Controller
in the management subnet over RDP. The device is up; NOC handed
you read-only operational creds.

## Connect

```sh
connect fw-dc-01
```

Any username/password works (NOC read-only). You'll land at the
operational-mode prompt `admin@FW-DC-01>`. To make config edits
you'd run `configure` (`admin@FW-DC-01#`) — not required here.

## You have

* A live PAN-OS CLI on `FW-DC-01` (via `connect`).

## You need to answer

Useful PAN-OS commands for this investigation:

```
show system info                            # version, model, uptime
show admins                                  # current admin accounts
show config running                          # full running config (XML)
show running security-policy                 # rulebase summary
show log globalprotect                       # GlobalProtect portal/gateway log
show log traffic                             # traffic log
show log system                              # system log (auth events, etc.)
show global-protect-gateway current-user     # who's on the VPN right now
```

Pipes work: `| include <re>`, `| begin <re>`, `| exclude <re>`,
`| count`. (PAN-OS XML config doesn't have Cisco-style sections;
prefer `| begin` to jump to a region and read forward, or pipe to
`| include` for line-level matches.)

1. Which PAN-OS authentication-profile name has no
   multi-factor-auth block configured?
2. From which source IP did the GlobalProtect password spray
   originate?
3. Which VPN username eventually logged in successfully after the
   brute force?
4. What is the internal destination IP the attacker hit on
   TCP/3389 from the VPN tunnel?
5. What is the name of the security rule that permitted the
   post-VPN pivot into the management subnet?

## Submitting answers

```sh
answer
answer 1 "<value>"
answer remember 1 "<value>"
answer reveal
```
