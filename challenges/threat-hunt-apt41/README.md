# threat-hunt-apt41

Educational threat-hunt scenario inspired by published APT41 activity.

## Scenario

An EDR alert flags an outbound HTTP request from an Exchange Server's
`REDACTED` worker process to an unfamiliar domain. The on-call hunter
(the player) is given SSH access to a triage box with copies of the
relevant logs and must answer five investigative questions to confirm
the intrusion and obtain the flag.

## Player workflow

```sh
ssh -p <port> hunter@<host>      # password: hunter
cat ~/investigation.md           # briefing + question list
ls ~/logs/                       # the artefact corpus
rg 'REDACTED' ~/logs             # ripgrep is installed
jq 'select(.Image | endswith("REDACTED"))' ~/logs/sysmon.json
answer                           # list open questions
answer remember 1 "REDACTED"     # save an answer locally
answer reveal                    # reveal the flag once all five are correct
```

## ATT&CK techniques covered

| ID | Technique | Where in the corpus |
|---|---|---|
| T1190 | Exploit Public-Facing Application (ProxyLogon, REDACTED) | `access.log` SSRF prefix, `iis_application.log` |
| T1505.003 | Web Shell | `REDACTED` upload + repeated POSTs with `cmd=…` parameter |
| T1059.001 | PowerShell | base64-encoded PS in `access.log` + `sysmon.json` |
| T1003.003 | NTDS | `esentutl /p ntds.dit` in `sysmon.json` |
| T1560.001 | Archive via WinRAR | `rar a -hp$Pass` |
| T1071.001 | Application Layer Protocol: Web | HTTP beacon to `REDACTED` |
| T1567.002 | Exfiltration to Cloud Storage | curl upload of 2.1 MB rar |

## D3FEND counters this exercises

| ID | Defense | Surface in the scenario |
|---|---|---|
| D3-FA   | File Analysis | `REDACTED` discovery via filesystem audit |
| D3-PSA  | Process Spawn Analysis | `REDACTED → REDACTED` parent/child anomaly |
| D3-OTF  | Outbound Traffic Filtering | Proxy log first-contact verdict |
| D3-UA   | User-Agent Analysis | Distinctive APT41-style UA on the beacon |
| D3-NTA  | Network Traffic Analysis | Periodic small beacons + one large upload |

## IOC fidelity

* **REDACTED** is real.
* **`REDACTED`** is a synthetic domain that doesn't
  resolve. Don't visit it.
* **`Mozilla/4.0 (compatible; MSIE 7.0; ...; APT41-Educational)`**
  is a synthetic User-Agent that follows APT41-style patterns but
  has the `-Educational` tag so it can never be confused for a real
  IOC.

## Author notes

* The web shell file (`REDACTED`) is named to match a common APT41
  habit of disguising shells as image files. The flag's plaintext
  hint embeds the same word.
* The proxy log includes a series of small (~512 byte) periodic
  requests followed by one large upload, mimicking real beacon →
  exfiltrate behaviour and giving the player a clue beyond just
  searching for the domain name.
* `iis_application.log` is deliberately written like a defender's
  triage notes, including the CVE citation. This makes the
  challenge solvable by a mid-level analyst without forcing them
  to recognise every IOC from memory.
