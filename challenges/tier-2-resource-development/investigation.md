# Investigation Briefing — Tier 2: Resource Development

Three weeks before the incident, the adversary built out their
staging kit in plain sight — registering lookalike domains,
minting certificates, standing up impersonator accounts, and
pre-staging a known offensive tool on a hosting provider. You
have WHOIS/CT/social-impersonation/tool-intel exports. Walk
them and identify each piece of pre-built infrastructure.

## You have

```
~/logs/whois-export.json
~/logs/impersonation-report.json
~/logs/tool-intel-feed.json
~/logs/ct-hits.json
```

## You need to answer

1. **What is the homoglyph lookalike domain the adversary
registered? (Bare domain, exactly as it appears in WHOIS.)**
   _hint: whois-export.json — find the entry where
`homoglyph_of=example.com`._

2. **What is the handle (the LinkedIn username, the slug after
`linkedin.com/in/`) of the impersonator-recruiter account?**
   _hint: impersonation-report.json — `platform=linkedin`,
`type=fabricated_persona`._

3. **What is the handle of the **compromised** (not fabricated)
X/Twitter account the adversary now controls? (Without
the `@`.)**
   _hint: impersonation-report.json — `platform=x` and
`type=account_takeover` (not `fabricated_persona`)._

4. **What is the SHA256 of the pre-staged tool the adversary
uploaded? (64-char lowercase hex.)**
   _hint: tool-intel-feed.json — the single entry with
`confidence=high` and `cluster_match=true`._

5. **What is the FQDN that the adversary minted a Let's
Encrypt certificate for, sitting on the lookalike domain?
(Full hostname as it appears in the CT record.)**
   _hint: ct-hits.json — find the issuer `Let's Encrypt` entry that
chains to the lookalike domain from question 1._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1583.001` — Acquire Infrastructure — Domains. The adversary registered a lookalike of `example.com` using a homoglyph substitution through a registrar that doesn't enforce DNSSEC.
* `T1585.001` — Establish Accounts — Social Media. A fresh LinkedIn profile claiming to be a recruiter at the target's HR vendor was created 18 days before the incident. The takedown vendor's report flagged it.
* `T1586.001` — Compromise Accounts — Social Media. Distinct from the fabricated persona above: the adversary also took over a real but dormant Twitter/X account belonging to a well-followed industry analyst, using its reputation to seed a poisoned link.
* `T1588.002` — Obtain Capabilities — Tool. The tool-intel feed records a pre-staged payload — a known C2 implant — uploaded to a cloud-bucket URL by an actor cluster matching this adversary's TTPs. The implant SHA256 was correlated to a public family.
* `T1608.001` — Stage Capabilities — Upload Malware. The same implant shows up in a certificate-transparency hit: a Let's Encrypt cert was minted for a subdomain of the lookalike domain pointing at the payload host, eight days before delivery.
