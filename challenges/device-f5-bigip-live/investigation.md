# Investigation Briefing — bigip-01 (Live)

`bigip-01` (F5 BIG-IP 2200S, BIG-IP 14.1.0) has been seen forwarding
HTTP header content to an unfamiliar external IP on UDP/514 over
the last 48 hours. Suspect: TMUI auth bypass / path-traversal of
the CVE-2020-5902 family. The device is up; NOC handed you
operational TMSH credentials.

## Connect

```sh
connect bigip-01
```

NOC creds — any username/password works for this exercise. You'll
land at the F5 `bigip-01(tmos)#` prompt.

## You have

* A live F5 TMSH on `bigip-01` (via `connect`).

## You need to answer

Useful TMSH commands:

```
show /sys version                       # software version
show /sys hardware                       # platform info
list /auth user                          # all TMSH users
list /ltm virtual                        # virtual servers
list /ltm rule                           # all iRules (Tcl source)
list /sys management-route               # management plane routes
show /sys log audit                      # AUDIT events
show httpd-log                           # (synthetic for this exercise)
                                         # TMUI HTTP access log
```

Pipes work — `| include`, `| exclude`, `| begin`, `| section`,
`| count`, `| grep`.

1. What unauthenticated path-traversal JSP filename did the
   attacker hit through the TMUI to dump files?
2. What is the username of the rogue admin account created via
   TMSH?
3. What is the name of the iRule that exfiltrates HTTP headers?
4. Which virtual server has the exfiltration iRule attached?
5. From which source IP did the attacker exploit the TMUI RCE?

## Submitting answers

```sh
answer
answer 1 "<value>"
answer remember 1 "<value>"
answer reveal
```
