# Investigation Briefing — Tier 2: Exfiltration

Same intrusion, five departments. The attacker tried five different
exfiltration paths to get data out. Identify the technique used
from each affected host.

## You have

```
~/logs/proxy.log
~/logs/dns_queries.log
~/logs/cli_history.log
~/logs/timeline.log
~/logs/watcher.log
```

## You need to answer

1. **On host FINANCE-2 the C2 channel exfiltrated approximately
how many MB? (Integer, no units.)**
   _hint: proxy.log — sum bytes_out for the host's beacon domain.
Spike from the usual ~500-byte beacon size is the giveaway._

2. **On host RND-7 which DNS record type is the attacker abusing
for the alternative exfiltration channel? (Upper-case
three-letter type, e.g. `TXT`.)**
   _hint: dns_queries.log — RND-7's queries land on an unfamiliar
SLD with a single record type repeated._

3. **What is the AWS S3 bucket name the attacker uploaded to
from host HR-3? (Just the bucket name, no s3:// prefix.)**
   _hint: cli_history.log — search for aws s3 cp commands._

4. **Between which two UTC hours does the attacker schedule
their daily exfiltration on host LEGAL-1? Answer as
HH:MM-HH:MM in 24-hour format.**
   _hint: timeline.log on LEGAL-1 — the exfil transfers all
share an identical hour window._

5. **On host MARKETING-2 the automated exfiltration script
monitors which folder for new files? (Full path as in
watcher.log.)**
   _hint: watcher.log — line with `watch_path=…` and `event=created`._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1041` — Exfiltration Over C2 Channel — the established HTTPS C2 also ferries out a 240 MB dump.
* `T1048.003` — Exfiltration Over Alternative Protocol — DNS A queries with base32 payloads to a different external NS.
* `T1567.002` — Exfiltration to Cloud Storage — aws s3 cp to an attacker bucket.
* `T1029` — Scheduled Transfer — exfiltration happens only between 02:00 and 03:00 UTC to blend with backup traffic.
* `T1020` — Automated Exfiltration — a script wakes on file-create in a watched folder and ships every new doc straight to attacker infra without human input.
