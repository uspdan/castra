# Investigation Briefing — Device Forensics: GlobalProtect MFA Gap

FW-DC-01 (PA-3220, PAN-OS 10.2) had an auth-profile gap that
let the attacker brute-force their way through GlobalProtect.
Once on the VPN they crossed a policy they shouldn't have. The
config, the GlobalProtect log, the post-VPN traffic log, and
the system log are staged for you.

## You have

```
~/logs/config.xml
~/logs/globalprotect.log
~/logs/traffic.log
~/logs/system.log
```

## You need to answer

1. **Which PAN-OS authentication profile name has no
multi-factor-auth block configured? (Exact name as it
appears in the XML.)**
   _hint: config.xml — under `<authentication-profile>` look for an
entry where the `<multi-factor-auth>` element is absent._

2. **From which source IP did the GlobalProtect password spray
originate? (Format x.x.x.x.)**
   _hint: globalprotect.log — count failed-login attempts by source
IP. One IP has 200+ in a tight time window._

3. **Which VPN username eventually logged in successfully after
the brute force? (Lowercase username only, no domain.)**
   _hint: globalprotect.log — same source IP as the previous
question; status=auth-success._

4. **What is the internal destination IP the attacker hit on
TCP/3389 from the VPN tunnel? (Format x.x.x.x.)**
   _hint: traffic.log — look for `app=ms-rdp` from the
GlobalProtect tunnel subnet (172.21.x.x) into the
management /24._

5. **What is the name of the security rule that permitted the
post-VPN pivot into the management subnet? (Exact rule
name as it appears in the XML and the traffic log.)**
   _hint: Cross-reference traffic.log's `rule=` field with the
`<entry name="...">` in the rulebase section of
config.xml._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1556.006` — Modify Authentication Process — Multi-Factor Authentication. One PAN-OS authentication-profile is missing the multi-factor-auth block, so users bound to that profile reach the VPN with password alone.
* `T1110` — Brute Force — a single source IP launched a password-spray against the GlobalProtect portal targeting one VPN account.
* `T1078` — Valid Accounts — the spray eventually succeeded against one contractor VPN user who, per the auth-profile gap, isn't MFA-protected.
* `T1021.001` — Remote Services — Remote Desktop Protocol. Post-VPN the session pivoted via RDP to a Domain Controller in the internal management subnet.
* `T1190` — Exploit Public-Facing Application (policy abuse) — a single PAN-OS security rule allowed gp-users -> mgmt-net for any app/service, when the intent was "GP users to corp web apps only".
