# Investigation Briefing — Tier 2: Initial Access

Five separate environments — corporate Office 365, a public web
server, an SSO portal, a VPN gateway, and a software supply
chain — each had one suspicious event in the last week. For
each environment, identify which ATT&CK technique was used for
initial access.

## You have

```
~/logs/office365_audit.log
~/logs/webapp_access.log
~/logs/sso_auth.log
~/logs/vpn_gateway.log
~/logs/supply_chain.log
```

## You need to answer

1. **In office365_audit.log, which user opened the malicious
attachment that triggered the macro chain? (Just the
UPN, e.g. user@corp.local.)**
   _hint: Filter for MailItemsAccessed + WordOrExcelMacroEnabled._

2. **In webapp_access.log, which CVE was used to compromise
the public web server? (Format: CVE-YYYY-NNNNN.)**
   _hint: Look for an LDAP-protocol JNDI string in a User-Agent or
header._

3. **In sso_auth.log, what country code does the successful
login come from that should have triggered an impossible-
travel alert? (Two-letter ISO code, uppercase.)**
   _hint: Compare the successful logon with the user's other
recent successful logons in the same file._

4. **In vpn_gateway.log, what is the attacker source IP that
successfully authenticated to the VPN after a port-scan
burst? (Format: x.x.x.x.)**
   _hint: The scan source and the successful logon share an IP.
Look for repeated TCP RST on closed ports preceding the
accepted login._

5. **In supply_chain.log, what is the SHA256 of the package
that was distributed by the compromised update server?
(Full hex string, lowercase.)**
   _hint: The compromised update server is the *only* upstream that
flipped its signing identity between consecutive
publishes._

## Submitting answers

```sh
answer                          # list open questions
answer 1 "<value>"              # single-shot validate
answer remember 1 "<value>"     # remember locally
answer reveal                   # reveal flag when all correct
```

## ATT&CK techniques chained

* `T1566.001` — Spearphishing Attachment — user opens malicious xlsm that spawns macro-driven powershell from Office.
* `T1190` — Exploit Public-Facing Application — Log4Shell probe followed by reverse-shell pull from the JNDI server.
* `T1078` — Valid Accounts — credential-stuffing into an SSO portal using a credential found in a recent dump.
* `T1133` — External Remote Services — VPN logon from an IP previously seen scanning multiple ports on the same gateway.
* `T1195.002` — Supply Chain Compromise — a trusted update server pushed a backdoored package signed with a stolen cert.
