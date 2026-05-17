# Investigation Briefing — NS-PERIM-01 (Live)

`NS-PERIM-01` (Citrix ADC / NetScaler MPX-15020, NS 13.1) was a
candidate target for the CVE-2023-3519 family. EDR on the
backend caught a one-shot connection from a host you don't
recognise to TCP/22 of a Domain Controller, sourced through the
appliance. The device is up; NOC handed you operational nscli
credentials.

## Connect

```sh
connect ns-perim-01
```

Any username/password works (NOC). You'll land at the
NetScaler `NS-PERIM-01> ` prompt.

## You have

* A live NetScaler CLI on `NS-PERIM-01` (via `connect`).

## You need to answer

Useful nscli commands here:

```
show ns version                  # software/build
show ns hardware                 # platform
show system user                 # admin / system users
show vserver                     # virtual servers
show running config              # full running config
show httpaccess                  # (synthetic for this exercise)
                                 # HTTP access log
show ns log                      # (synthetic for this exercise)
                                 # /var/log/ns.log
```

Pipes work — `| include`, `| exclude`, `| begin`, `| count`.

1. What URL path did the attacker POST to for the initial
   unauthenticated RCE?
2. What is the filename of the webshell dropped under
   `/var/netscaler/logon/themes/`?
3. What is the username of the rogue system user with superuser
   binding?
4. From which source IP did the attacker exploit the Gateway and
   access the webshell?
5. Which load-balancing virtual server did the attacker
   create / configure to expose a backend service on TCP/22 to
   the internet?

## Submitting answers

```sh
answer
answer 1 "<value>"
answer remember 1 "<value>"
answer reveal
```
