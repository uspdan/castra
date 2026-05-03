# YARA Rule Writer

## Overview
Write a YARA rule to detect 5 malware samples out of 20 total files without false positives.

## Solution

1. Download and analyze the sample files
2. Malware samples contain these unique indicators:
   - XOR-encoded string "SIEGE_MALWARE_BEACON" (XOR key 0x5A)
   - Mutex name "Global\SiegeRangeC2Mutex" in plaintext
   - User-agent "Mozilla/5.0 SiegeAgent/1.0" in plaintext
3. Benign files contain partial matches (e.g., "Global\SystemHealthCheck") so be specific

### Working YARA rule:
```yara
rule siege_malware {
    strings:
        $mutex = "Global\\SiegeRangeC2Mutex"
        $ua = "SiegeAgent/1.0"
    condition:
        $mutex and $ua
}
```

Or simply:
```yara
rule siege_malware {
    strings:
        $mutex = "Global\\SiegeRangeC2Mutex"
    condition:
        $mutex
}
```

## Flag
`CTF{REDACTED}`
