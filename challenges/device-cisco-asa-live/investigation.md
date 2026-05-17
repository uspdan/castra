# Investigation Briefing — ASA-VPN-01 (Live)

`ASA-VPN-01` (Cisco ASA 5516, 9.16(3)19) is your AnyConnect head-end.
EDR caught an RDP session from a tunnel-IP to a Domain Controller
in the management subnet — pivoting through the VPN tunnel from a
public IP that had no business succeeding at auth.

## Connect

```sh
connect asa-vpn-01
```

Any user/password. `enable` password: `n0c-l3v3l-15`.

## You have

A live ASA CLI on `ASA-VPN-01` via `connect`.

## You need to answer

```
show vpn-sessiondb anyconnect       # active VPN sessions
show tunnel-group-info               # tunnel-group → group-policy map
show running-config                  # priv mode — full config
show logging                         # priv mode — auth + connection events
show webvpn statistics
```

1. Tunnel-group name with MFA disabled on its default group-policy.
2. Authentication server group bound to that tunnel-group.
3. VPN username that logged in successfully.
4. Source IP of the brute-force / successful login.
5. Internal IP the attacker pivoted to over TCP/3389.

## Submit

```sh
answer
answer 1 "<value>"
answer reveal
```
