# Investigation Briefing — Device Forensics: FortiGate Auth Bypass

FGT-PERIM-02 (FortiGate 100F, FortiOS 7.2.4) shipped a config
change at 02:11 UTC last night that nobody on the team owns up
to. The HTTPS admin access log, system event log, and a config
diff are staged for you. Reconstruct exactly how the attacker
got in, who they became, and what they changed.

## You have

```
~/logs/admin-https.log
~/logs/system-event.log
~/logs/config-diff.txt
~/logs/approved-admins.txt
```

## You need to answer

1. **What value did the attacker put in the `Forwarded:` header's
`for=` parameter to trigger the auth bypass? (Exact value
as it appears after `for=` and before the next semicolon
or end of header.)**
   _hint: admin-https.log — requests with `Forwarded: for=...;
by=...` immediately before the rogue admin appears. The
canonical CVE-2022-40684 trick uses a specific local-looking
identity here._

2. **What is the username of the rogue super_admin account
added during the bypass window? (Lowercase, as it appears
in the config diff.)**
   _hint: config-diff.txt — the `+config system admin / + edit ...`
block. The legitimate roster (in approved-admins.txt) does
not contain it._

3. **Which FortiOS admin profile setting did the attacker leave
unrestricted on the rogue account so it would accept
logins from any source IP? (Exact CLI config keyword.)**
   _hint: config-diff.txt for that account — look for the absence /
wildcard of `REDACTED`._

4. **Which CIDR was added to the SSL-VPN portal's split-tunnel
routing-address list to expose the internal management
subnet? (Format x.x.x.x/yy.)**
   _hint: config-diff.txt — within `config vpn ssl web portal / edit
full-access`, look for the new entry under
`set split-tunneling-routing-address` or a referenced
firewall address group._

5. **What is the source IP from which the rogue admin
subsequently authenticated via the web GUI? (Format x.x.x.x.)**
   _hint: system-event.log — `event=login` with `status=success`
and the new username from the previous question._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1190` — Exploit Public-Facing Application — the auth bypass exploits a request where a specific Forwarded `for=` value tricks the backend into treating the call as a local trusted request.
* `T1078.003` — Valid Accounts — Local Accounts. The attacker created a new super_admin local user via the bypassed API.
* `T1556` — Modify Authentication Process — the attacker disabled trusted-host enforcement on their new admin, allowing it to log in from anywhere.
* `T1098` — Account Manipulation — after the rogue admin existed, they modified the SSL-VPN portal config to add a wildcard split- tunnel route that exposes the internal management subnet.
* `T1078` — Valid Accounts (post-create login) — the attacker, having added the admin, immediately logged in via the GUI.
