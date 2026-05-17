# Investigation Briefing — IOSXE-EDGE-01 (Live)

`IOSXE-EDGE-01` (Cisco Catalyst 8500, IOS XE 17.9.1a) is your
internet edge. Talos posted an advisory yesterday about a WebUI
auth-bypass family (CVE-2023-20198 + CVE-2023-20273). You're not
sure if you got hit — find out.

## Connect

```sh
connect iosxe-edge-01
```

NOC creds — any user/password. Then `enable` with the NOC
break-glass password `n0c-l3v3l-15`.

## You have

* A live IOS XE CLI on `IOSXE-EDGE-01` (via `connect`).
* `~/approved-users.txt` — authorised local users.

## You need to answer

```
show running-config | include privilege 15   # local priv-15 users
show users                                    # live sessions
show webui-log                                # synthetic — WebUI access log
show logging                                  # priv mode — message log
show ip http server status                    # WebUI + bound ports
show platform software process list           # FP_0 processes
```

1. Username of the rogue privilege-15 local user.
2. Source IP of the WebUI exploit traffic.
3. The URL-encoded path the attacker POSTed to for the WSMA
   bypass (exact, as it appears in the WebUI log).
4. The TCP port the Lua implant is listening on.
5. The process name the implant runs as on FP_0.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
