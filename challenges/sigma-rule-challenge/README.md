# Sigma Rule Challenge

## Solution
Write a Sigma rule that detects both attack patterns:

```yaml
title: Detect Encoded PowerShell and Suspicious Scheduled Tasks
status: experimental
logsource:
    category: process_creation
    product: windows
detection:
    sel_powershell:
        Image|endswith: '\powershell.exe'
        CommandLine|contains: '-EncodedCommand'
    sel_schtasks:
        Image|endswith: '\schtasks.exe'
        CommandLine|contains:
            - '/create'
            - 'AppData'
    condition: sel_powershell or sel_schtasks
level: high
```

Flag: `CTF{REDACTED}`
