# Investigation Briefing — pfsense-edge-01 (Live)

`pfsense-edge-01` (pfSense 2.7.0-RELEASE on a small Atom box) is a
branch perimeter firewall. WAN-side WebGUI was left enabled
during a recent reorg. Threat-intel flagged the WAN IP for a
suspicious port mapping over the last 48 hours.

## Connect

```sh
connect pfsense-edge-01
```

Any user/password.

## You have

A live pfSense shell on `pfsense-edge-01` via `connect`. The
commands wrap `/conf/config.xml`, `pfctl`, and the FreeBSD
syslog files.

## You need to answer

```
show version
show users                # config.xml's <system><user> entries
show config               # full /conf/config.xml
show rules                # pfctl -s rules
show nat                  # pfctl -s nat
show auth-log             # nginx auth + webconfigurator events
show log filter           # pf filter log (filterlog)
show log system           # PHP-FPM webconfigurator audit
```

1. Username of the rogue admin account.
2. Source IP of the successful WebGUI login.
3. `descr` of the rogue NAT rule.
4. Internal target IP the NAT rule forwards to.
5. WAN port the NAT rule listens on.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
