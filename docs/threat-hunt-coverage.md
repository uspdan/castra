# Threat-Hunt Coverage — ATT&CK + D3FEND

Live coverage map of every Siege Range threat-hunt challenge against
the MITRE ATT&CK Enterprise matrix and the D3FEND defensive technique
matrix. Updated as each scenario lands.

Two tiers of scenarios:

* **Tier 1 — narrative actor scenarios.** Rich, story-driven hunts
  modelled on published real-world activity from named threat groups.
  Each one chains 5-10 techniques realistically.
* **Tier 2 — tactic mini-campaigns.** Factory-generated 5-10
  technique chains, one per ATT&CK tactic. Focused on technique
  *coverage* rather than narrative depth.

A technique is considered "covered" once at least one scenario both
(a) emits a log artefact a hunter must use to answer a question, and
(b) cites the technique ID in its manifest's `mitre_techniques`.

## Tier 1 — narrative actor scenarios

| Slug | Actor | Status | ATT&CK techniques (manifest) |
|------|-------|--------|------------------------------|
| `threat-hunt-apt41` | APT41 | ✅ shipped | T1190, T1505.003, T1059.001, T1071.001, T1567.002 |
| `threat-hunt-volt-typhoon` | Volt Typhoon | ⏳ planned | T1059.001, T1078, T1003.003, T1090, T1133 |
| `threat-hunt-salt-typhoon` | Salt Typhoon | ⏳ planned | T1190, T1133, T1041, T1095 |
| `threat-hunt-midnight-blizzard` | APT29 / Midnight Blizzard | ⏳ planned | T1528, T1098.005, T1114.002, T1078.004 |
| `threat-hunt-scattered-spider` | UNC3944 | ⏳ planned | T1566.004, T1621, T1556, T1486 |
| `threat-hunt-shiny-hunters` | ShinyHunters | ⏳ planned | T1539, T1078, T1567.001, T1530 |
| `threat-hunt-cl0p` | Cl0p | ⏳ planned | T1190, T1505.003, T1567, T1486 |
| `threat-hunt-lazarus-defi` | Lazarus | ⏳ planned | T1566.002, T1204.001, T1565.003 |

## Tier 2 — tactic mini-campaigns (ATT&CK Enterprise)

Each campaign chains 5-10 techniques within a single tactic. Factory
output, light hand-tuning. One per tactic. 14 total.

| Tactic | ID | Status | Techniques (planned) |
|--------|-----|--------|----------------------|
| Reconnaissance | TA0043 | ✅ shipped (`tier-2-reconnaissance`) | T1595.002, T1589.002, T1592, T1591.001, T1596.005 |
| Resource Development | TA0042 | ✅ shipped (`tier-2-resource-development`) | T1583.001, T1585.001, T1586.001, T1588.002, T1608.001 |
| Initial Access | TA0001 | ✅ shipped (`tier-2-initial-access`) | T1566.001, T1190, T1078, T1133, T1195.002 |
| Execution | TA0002 | ✅ shipped (`tier-2-execution`) | T1059.001, T1059.003, T1053.005, T1106, T1204.002 |
| Persistence | TA0003 | ✅ shipped (`tier-2-persistence`) | T1547.001, T1053.005, T1543.003, T1546.003, T1197 |
| Privilege Escalation | TA0004 | ✅ shipped (`tier-2-privilege-escalation`) | T1548.001, T1055.001, T1134.001, T1078.003, T1548.002 |
| Defense Evasion | TA0005 | ✅ shipped (`tier-2-defense-evasion`) | T1070.006, T1070.001, T1218.011, T1027.002, T1036.005 |
| Credential Access | TA0006 | ✅ shipped (`tier-2-credential-access`) | T1003.001, T1558.003, T1003.006, T1555.003, T1552.004 |
| Discovery | TA0007 | ✅ shipped (`tier-2-discovery`) | T1018, T1083, T1087.002, T1057, T1135 |
| Lateral Movement | TA0008 | ✅ shipped (`tier-2-lateral-movement`) | T1021.001, T1021.002, T1047, T1053.005, T1021.003 |
| Collection | TA0009 | ✅ shipped (`tier-2-collection`) | T1005, T1056.001, T1119, T1115, T1074.001 |
| Command and Control | TA0011 | ✅ shipped (`tier-2-command-and-control`) | T1071.001, T1071.004, T1102.002, T1573.002, T1090.002 |
| Exfiltration | TA0010 | ✅ shipped (`tier-2-exfiltration`) | T1041, T1048.003, T1567.002, T1029, T1020 |
| Impact | TA0040 | ✅ shipped (`tier-2-impact`) | T1486, T1490, T1561.001, T1485, T1531 |

## Network Device Forensics

Vendor-specific blue-team scenarios where the player investigates a
compromised or misconfigured network device. Same SSH-into-container +
`answer` CLI runtime as the threat-hunt mini-campaigns; corpus is
device configs / show-output / device logs rather than host telemetry.

| Slug | Vendor | Status | ATT&CK techniques (manifest) |
|------|--------|--------|------------------------------|
| `device-cisco-ios` | Cisco IOS 15.7 (2911 ISR) — **static logs** | ✅ shipped | T1078, T1078.001, T1133, T1562.004, T1021.004 |
| `device-cisco-ios-live` | Cisco IOS 15.7 (2911 ISR) — **live CLI sim** | ✅ shipped | T1078, T1078.001, T1133, T1562.004, T1021.004 |
| `device-fortigate-cve` | FortiGate / FortiOS 7.2 (CVE-2022-40684-style) — **static logs** | ✅ shipped | T1190, T1078.003, T1556, T1098, T1078 |
| `device-fortigate-live` | FortiGate / FortiOS 7.2 — **live CLI sim** | ✅ shipped | T1190, T1078.003, T1556, T1098, T1078 |
| `device-paloalto-vpn` | Palo Alto PAN-OS 10.2 (GlobalProtect MFA gap) — **static logs** | ✅ shipped | T1556.006, T1110, T1078, T1021.001, T1190 |
| `device-paloalto-live` | Palo Alto PAN-OS 10.2 — **live CLI sim** | ✅ shipped | T1556.006, T1110, T1078, T1021.001, T1190 |
| `device-f5-bigip-live` | F5 BIG-IP 14.1 — **live CLI sim** (CVE-2020-5902 TMUI RCE) | ✅ shipped | T1190, T1078, T1071.001, T1556, T1021.001 |
| `device-citrix-netscaler-live` | Citrix NetScaler 13.1 — **live CLI sim** (CVE-2023-3519 family) | ✅ shipped | T1190, T1505.003, T1078, T1021.001, T1133 |
| `device-cisco-iosxe-live` | Cisco IOS XE 17.9 — **live CLI sim** (CVE-2023-20198 WebUI bypass + Lua implant) | ✅ shipped | T1078, T1190, T1505.003 |
| `device-cisco-asa-live` | Cisco ASA 9.16 / AnyConnect — **live CLI sim** (contractor tunnel-group MFA gap) | ✅ shipped | T1556.006, T1078, T1110, T1021.001 |
| `device-juniper-junos-live` | Juniper SRX 340 / Junos 21.2 — **live CLI sim** (stolen-creds commit / rogue super-user) | ✅ shipped | T1078, T1556, T1562.004, T1071.001 |
| `device-mikrotik-routeros-live` | MikroTik RouterOS 7.10 — **live CLI sim** (Winbox + scheduler persistence, VPNFilter-style) | ✅ shipped | T1053, T1078, T1071.001, T1133, T1021.004 |
| `device-pfsense-live` | pfSense 2.7 — **live CLI sim** (WebGUI brute force + WAN-side NAT pivot) | ✅ shipped | T1078, T1110, T1133, T1021.004 |
| `device-aruba-clearpass` | Aruba ClearPass / AOS-CX | ⏳ planned | TBD |

## Windows / Active Directory Forensics

Same SSH-into-container + ``connect <host>`` pattern as the network-device
track; the device shell engine adopts PowerShell-style prompts and cmdlets
via the per-device hooks. Engine gained case-insensitive command matching
(real Cisco IOS and PowerShell are both case-insensitive) so ``Get-ADUser``
and ``get-aduser`` resolve identically.

| Slug | Host | Story | ATT&CK techniques |
|------|------|-------|-------------------|
| `windows-dc-live` | DC01.corp.local — Windows Server 2022 AD DS | Kerberoast → DCSync → AdminSDHolder backdoor | T1558.003, T1078, T1003.006, T1098 |
| `windows-endpoint-live` | WS-FIN-04 — Windows 11 finance workstation | Macro → encoded PowerShell → dropped binary → scheduled-task persistence → C2 | T1204.002, T1059.001, T1053.005, T1071.001, T1547 |
| `windows-fileserver-live` | FS-CORP-01 — Windows Server 2022 SMB file server | Lateral logon (4624 t3) → vssadmin shadow delete → service-installed persistence → encryption staging | T1021.002, T1078, T1490, T1543.003, T1074.001 |
| `windows-exchange-live` | EXCH-01 — Exchange 2019 CU12 (unpatched ProxyShell) | AutoDiscover SSRF → /Powershell RPS → New-MailboxExportRequest → .pst exfil via .aspx webshell | T1190, T1505.003, T1114.002, T1567 |
| `windows-iis-live` | IIS-WEB-01 — Windows Server 2019 IIS 10 | .aspx upload → w3wp spawns REDACTED → nc.exe download → TCP/1433 pivot to MSSQL | T1505.003, T1190, T1059.003, T1105, T1021.002 |

## Linux Host Forensics

Live bash session against a compromised Linux host. Same SSH-into-container
+ ``connect <host>`` pattern; engine renders a RHEL/Debian-style bash
prompt and exposes shell commands as the grammar's top-level keys.

| Slug | Host | Story | ATT&CK techniques |
|------|------|-------|-------------------|
| `linux-syslog-live` | lnx-web-02 — RHEL 9.3 Apache+Tomcat | SSH brute force → REDACTED privesc → /etc/cron.d/ persistence → /dev/tcp reverse shell | T1110, T1078, T1068, T1053.003, T1071.001 |

## D3FEND coverage (defensive-counter side)

Listed by D3FEND category. A scenario "covers" a defense if the
hunter must apply that defensive analysis technique to answer a
question.

### Detect

| D3FEND ID | Technique | Covered by |
|-----------|-----------|------------|
| D3-FA | File Analysis | `threat-hunt-apt41` (web-shell file discovery) |
| D3-PSA | Process Spawn Analysis | `threat-hunt-apt41` (w3wp→cmd parent pivot) |
| D3-UA | User-Agent Analysis | `threat-hunt-apt41` (beacon UA) |
| D3-NTA | Network Traffic Analysis | `threat-hunt-apt41` (beacon→exfil rate change) |
| D3-OTF | Outbound Traffic Filtering | `threat-hunt-apt41` (first-contact verdict) |
| D3-CSPP | Command and Scripting Param Probing | _planned_ |
| D3-FCA | File Creation Analysis | _planned_ |
| D3-PA | Process Analysis | _planned_ |
| D3-DA | Domain Analysis | _planned_ |
| D3-IRA | IP Reputation Analysis | _planned_ |

### Isolate / Harden / Evict / Deceive

These categories are surfaced in scenarios that ask the hunter to
recommend a containment or eviction step. Planned for the
`tier-2-impact` mini-campaign.

## How to update this file

When a new challenge lands:

1. Add a row in the appropriate Tier 1 or Tier 2 table.
2. For every ATT&CK technique the scenario *requires the hunter to
   touch*, add it to the technique-id list (deduplicated).
3. For every D3FEND defense the scenario exercises, add a row in
   the D3FEND table (or update the existing row's "covered by"
   list).
4. Commit alongside the challenge in the same commit.

When a technique is covered by ≥ 3 distinct scenarios, the entry can
be marked **redundant** — that's the signal authors should pick a
different gap to fill.

## Coverage targets (Sprint 14+ goal)

* **Tier 1:** 8 narrative actor scenarios complete (1/8 ✅).
* **Tier 2:** 14 tactic mini-campaigns complete (9/14 ✅).
* **ATT&CK technique floor:** every Enterprise tactic has ≥ 1
  technique covered by ≥ 1 scenario (currently 7/14 tactics
  touched via the APT41 scenario).
* **D3FEND defense floor:** at least 1 technique under each of
  the 6 D3FEND base categories.
