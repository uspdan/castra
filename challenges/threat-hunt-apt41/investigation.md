# Investigation Briefing — Suspected APT41 Intrusion

**Timeline:** Last 48 hours.
**Affected host:** `EX01.contoso.local` — Exchange 2019 server, public-facing OWA.
**Initial signal:** EDR flagged an outbound HTTP request from `REDACTED` to an unfamiliar
domain. Triage that lead and confirm or refute compromise.

## You have

```
~/logs/access.log          IIS access log from the public-facing OWA listener.
~/logs/sysmon.json         Sysmon EID 1 (ProcessCreate) events for the last day.
~/logs/proxy.log           Outbound web-proxy log (CSV: timestamp, src_ip, host, ua, bytes).
~/logs/iis_application.log Application errors / 500s from the IIS app.
```

## You need to answer

1. **Which web shell file did the attacker drop in the `/uploads/` tree?**
   (Filename only — e.g., `something.aspx`.)

2. **What is the immediate parent process of the malicious `REDACTED` spawn?**
   (Process image filename — e.g., `explorer.exe`.)

3. **What external domain did the attacker exfiltrate data to?**
   (Bare domain, no scheme — e.g., `attacker.example.com`.)

4. **What User-Agent string does the C2 beacon use?**
   (Submit verbatim from the proxy log.)

5. **Which CVE did the attacker exploit for initial access?**
   (Format: `CVE-YYYY-NNNNN`.)

## Submitting answers

```sh
answer                          # list the open questions
answer 1 "REDACTED"             # submit one answer (single-shot validation)
answer remember 1 "REDACTED"    # remember an answer locally
answer reveal                   # attempt to reveal the flag once all five are remembered correctly
```

## Notes

* This is an **educational** scenario. The CVE is real; the domain
  and User-Agent are synthetic but follow APT41-style conventions.
  Treat published APT41 reporting (Mandiant M-Trends, US-CERT
  AA20-275A) as additional context if you want to see the real ones.
* The flag is `CTF{REDACTED}` — submit it back to Siege Range to score
  the challenge.
