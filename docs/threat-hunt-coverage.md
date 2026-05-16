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
| Reconnaissance | TA0043 | ⏳ planned | T1595.002, T1589.002, T1592, T1591.001, T1596.005 |
| Resource Development | TA0042 | ⏳ planned | T1583.001, T1585.001, T1586.001, T1588.002 |
| Initial Access | TA0001 | ⏳ planned | T1566.001, T1190, T1133, T1078.004, T1195.002 |
| Execution | TA0002 | ⏳ planned | T1059.001, T1059.003, T1053.005, T1106, T1204.002 |
| Persistence | TA0003 | ⏳ planned | T1547.001, T1543.003, T1098.001, T1136.001, T1505.003 |
| Privilege Escalation | TA0004 | ⏳ planned | T1548.001, T1055.001, T1134.001, T1078.003 |
| Defense Evasion | TA0005 | ⏳ planned | T1070.004, T1027, T1218.011, T1140, T1562.001 |
| Credential Access | TA0006 | ⏳ planned | T1003.001, T1110.001, T1555.003, T1558.003, T1552.004 |
| Discovery | TA0007 | ⏳ planned | T1018, T1083, T1087.002, T1057, T1135 |
| Lateral Movement | TA0008 | ✅ shipped (`tier-2-lateral-movement`) | T1021.001, T1021.002, T1047, T1053.005, T1021.003 |
| Collection | TA0009 | ⏳ planned | T1005, T1056.001, T1119, T1115, T1074.001 |
| Command and Control | TA0011 | ⏳ planned | T1071.001, T1071.004, T1573.002, T1572, T1090.002 |
| Exfiltration | TA0010 | ⏳ planned | T1041, T1048.003, T1567.002, T1029, T1020 |
| Impact | TA0040 | ⏳ planned | T1486, T1490, T1485, T1561.001, T1496 |

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
* **Tier 2:** 14 tactic mini-campaigns complete (1/14 ✅).
* **ATT&CK technique floor:** every Enterprise tactic has ≥ 1
  technique covered by ≥ 1 scenario (currently 7/14 tactics
  touched via the APT41 scenario).
* **D3FEND defense floor:** at least 1 technique under each of
  the 6 D3FEND base categories.
