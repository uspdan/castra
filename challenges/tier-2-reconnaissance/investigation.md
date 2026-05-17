# Investigation Briefing — Tier 2: Reconnaissance

Two weeks before the intrusion, somebody spent five days quietly
fingerprinting your perimeter, scraping employee directories,
and pinging your public databases. Your TI team has handed over
WAF logs, a passive-DNS slice, a LinkedIn-scrape evidence
bundle, and a Shodan-style external-asset report. Walk them and
identify the recon footprint.

## You have

```
~/logs/waf.log
~/logs/linkedin-scrape-evidence.json
~/logs/external-asset-report.json
~/logs/passive-dns-slice.log
```

## You need to answer

1. **What is the source IP that drove the bulk
vulnerability-template scan? (Format x.x.x.x.)**
   _hint: waf.log — sort by ip count; the obvious outlier has a
user-agent containing the scanner name._

2. **Which email-address format did the scraper infer from
the scrape? (Format string with `{first}` / `{last}`
placeholders — e.g. `REDACTED`.)**
   _hint: linkedin-scrape-evidence.json — the `inferred_email_pattern`
field is right there._

3. **Which exact server-version string from your edge fleet
ended up in the adversary's catalogue? (As it appears
in the Server response header — verbatim.)**
   _hint: waf.log — look at the `Server` header field for the
records where the scanner IP probed `/` and the WAF
passed them through._

4. **Which city did the adversary's enrichment pass identify
as the company's primary engineering office? (City name
only.)**
   _hint: linkedin-scrape-evidence.json — the `primary_eng_site`
block has a city field._

5. **Which corp hostname did the external scan-database
report flag as having an exposed admin panel? (Bare
hostname, no scheme, as it appears in the asset report.)**
   _hint: external-asset-report.json — the `flagged_assets` list
has one entry with `exposure=admin_panel`._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1595.002` — Active Scanning — Vulnerability Scanning. The adversary drove a Nuclei-style template scanner from a single cloud IP, hammering ~3000 distinct paths per minute with a recognisable user-agent.
* `T1589.002` — Gather Victim Identity Information — Email Addresses. A separate IP scraped LinkedIn and the corp `/about` / `/people` pages, harvesting a structured list of employees and email patterns.
* `T1592` — Gather Victim Host Information. The same scanner IP later came back with low-and-slow asset-fingerprinting requests against specific endpoints, harvesting precise server version strings from response headers.
* `T1591.001` — Gather Victim Org Information — Determine Physical Locations. The scrape includes a separate enrichment pass hitting Google Maps and the corp careers page to map office locations and the headcount per site.
* `T1596.005` — Search Open Technical Databases — Scan Databases. The adversary pulled the Shodan/Censys-equivalent report for every IP block your ASN advertises and flagged one host with an exposed admin panel from a stale staging deploy.
