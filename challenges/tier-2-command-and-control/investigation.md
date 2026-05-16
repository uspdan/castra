# Investigation Briefing — Tier 2: Command and Control

Five compromised hosts in five business units each picked a
different way to talk to their handler. You have summarised pcap
flow tables, DNS query logs, and a proxy log. Identify the C2
technique used by each host.

## You have

```
~/logs/flows.csv
~/logs/dns_queries.log
~/logs/proxy.log
~/logs/known_good_ja3.txt
```

## You need to answer

1. **Which fully-qualified domain is HOST-A beaconing to? (Bare
domain, no scheme.)**
   _hint: flows.csv host=HOST-A — look for periodic ~500 byte POSTs
with a regular cadence._

2. **What is the second-level domain HOST-B is using for DNS
tunnelling? (e.g. `dnsc2.example`.)**
   _hint: dns_queries.log — many long subdomain labels under the
same parent, all TXT records._

3. **Which web-service host is HOST-C using for bidirectional
comms? (Bare host name as it appears in the proxy log.)**
   _hint: proxy.log — find the host with both GET and POST traffic
from HOST-C where the user-agent isn't a normal browser._

4. **What is the JA3 hash recorded for the suspicious TLS
client HOST-D is using? (32-char hex string, lowercase.)**
   _hint: flows.csv lines with host=HOST-D and proto=tls have a
ja3 field. Cross-reference against the known-good list
in known_good_ja3.txt — one JA3 isn't there._

5. **What is the residential IP HOST-E is using as its
external proxy hop? (Format x.x.x.x.)**
   _hint: flows.csv host=HOST-E — the only direct upstream IP
outside the corp /16 range, and its rDNS resolves to
a residential ISP block._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1071.001` — Web Protocols (HTTPS POST) — classic beacon, ~500 byte POSTs every 60 seconds to a cloud-fronted domain.
* `T1071.004` — DNS Tunneling — HOST-B exfiltrates data inside subdomain labels of TXT queries to its own NS.
* `T1102.002` — Bidirectional Communication via Web Service — HOST-C beacons via a public pastebin / GitHub Gist style service rather than a dedicated domain.
* `T1573.002` — Encrypted Channel — Asymmetric Crypto — HOST-D talks over a custom TLS that doesn't match common JA3 fingerprints.
* `T1090.002` — External Proxy — HOST-E reaches the internet only through a single hop that itself sits at a residential ISP, with all C2 hops looking like normal HTTP through that proxy.
