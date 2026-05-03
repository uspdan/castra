# Phishing Investigation

## Overview
Analyze a simulated email inbox with 10 emails. One is a phishing attempt. Identify it and extract the flag.

## Solution

1. Browse the inbox and examine each email
2. Email #3 from "IT Support <support@c0mpany-secure.com>" is suspicious:
   - The domain uses a zero instead of 'o': `c0mpany-secure.com` vs `company.com`
   - The originating IP is `185.100.87.42` (external) vs `10.0.0.x` for all others
   - SPF check shows `Fail`
   - Urgent language pressuring immediate action
3. The email body contains a base64-encoded string: `aHR0cDovL2V2aWwuZXhhbXBsZS5jb20vc3RlYWw/ZmxhZz1DVEZ7cGgxc2hfMW52M3N0MWc0dDN9`
4. Decode it: `echo "aHR0cDovL2V2aWwuZXhhbXBsZS5jb20vc3RlYWw/ZmxhZz1DVEZ7cGgxc2hfMW52M3N0MWc0dDN9" | base64 -d`
5. Result: `http://evil.example.com/steal?flag=CTF{REDACTED}`

## Flag
`CTF{REDACTED}`
