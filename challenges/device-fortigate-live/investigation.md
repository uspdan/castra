# Investigation Briefing — FGT-PERIM-02 (Live)

`FGT-PERIM-02` (FortiGate 100F, FortiOS 7.2.4) shipped a config
change at 02:11 UTC last night that nobody on the team owns up to.
The device is still in production. NOC has handed you read-only
credentials for the box.

## Connect

```sh
connect fgt-perim-02
```

Any username/password works for this exercise (NOC read-only).

## You have

* A live FortiOS CLI on `FGT-PERIM-02` (via `connect`).
* `~/approved-admins.txt` — the NOC's authorised admin roster
  (last reviewed 2026-04-15).

## You need to answer

Use FortiOS commands — these are the most useful here:

```
get system status                       # version / build
show system admin                       # all admins, profile + trusthosts
show full-configuration                 # full config dump
show vpn ssl web portal                 # SSL VPN portal config
execute log display                     # current event log page
show admin-https-log                    # (synthetic for this exercise)
                                        # HTTPS admin API access log
```

Pipes work (`| include`, `| exclude`, `| section`, `| begin`,
`| grep`).

1. What value did the attacker put in the `Forwarded:` header's
   `for=` parameter to trigger the auth bypass?
2. What is the username of the rogue super_admin account?
3. Which FortiOS admin profile setting did the attacker leave
   unrestricted on the rogue account so it accepts logins from
   any source IP?
4. Which CIDR was added to the SSL-VPN portal's split-tunnel
   routing-address list?
5. What is the source IP from which the rogue admin
   subsequently authenticated via the web GUI?

## Submitting answers

```sh
answer
answer 1 "<value>"
answer remember 1 "<value>"
answer reveal
```
