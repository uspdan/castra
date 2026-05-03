# Splunk Threat Hunt

## Overview
Search through 10,000 security log entries to identify a brute force SSH attack and validate your findings.

## Solution

1. Search for "Failed password" to see failed login attempts
2. Notice 500 failed attempts for user "admin" from IP `10.0.0.47` within a 10-minute window
3. Search for "Accepted password" and "10.0.0.47" to find the successful login
4. The successful login timestamp is `2024-03-15T14:23:47Z`
5. Submit: IP=`10.0.0.47`, Username=`admin`, Timestamp=`2024-03-15T14:23:47Z`

## Flag
`CTF{REDACTED}`
