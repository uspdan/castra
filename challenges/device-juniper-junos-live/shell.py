"""Tiny vendor-CLI simulator engine.

Knows about: prompts, a user/privileged/config mode stack, prefix
matching, pipes (include / exclude / begin / section / count), and
Cisco-style error parity ("% Invalid input...", "% Ambiguous
command", "% Incomplete command.").

Does NOT know about: any specific vendor. Vendor specifics live in
a "device module" Python file passed on the command line, declaring:

    HOSTNAME              str
    BANNER                str   (printed before auth)
    GRAMMAR               dict  (command tree — see below)
    PRELOADED_HISTORY     list[str] (optional — what `show history` returns)

Grammar shape:

    GRAMMAR = {
        "show": {
            "running-config": {"fn": handler, "min_mode": "privileged"},
            ...
        },
        "enable": {"fn": handler, "min_mode": "user"},
        ...
    }

Leaves are dicts with an "fn" key (the handler). Anything else is
a descend node. Handlers receive (shell, remaining_tokens) and
return a string to print, or "" for no output.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
from typing import Optional

MODE_USER = "user"
MODE_PRIV = "privileged"
MODE_CONFIG = "config"
_MODE_ORDER = [MODE_USER, MODE_PRIV, MODE_CONFIG]

# Cisco-flavoured defaults. Per-device modules override by declaring
# PROMPT_SUFFIXES / PROMPT_FORMAT / AUTH_BANNER / AUTH_USERNAME_PROMPT /
# AUTH_PASSWORD_PROMPT.
_DEFAULT_PROMPT_SUFFIXES = {
    MODE_USER: ">",
    MODE_PRIV: "#",
    MODE_CONFIG: "(config)#",
}


class Shell:
    def __init__(self, device_mod) -> None:
        self.dev = device_mod
        self.hostname: str = device_mod.HOSTNAME
        self.grammar: dict = device_mod.GRAMMAR
        self.mode: str = MODE_USER
        # Pre-loaded history is what the *previous user* (the attacker)
        # left behind. The player can `show history` and read it.
        self.history: list[str] = list(getattr(device_mod, "PRELOADED_HISTORY", []))

    # ------------------------------------------------------------------
    # Prompt + banner + auth
    # ------------------------------------------------------------------

    def prompt(self) -> str:
        suffixes = getattr(self.dev, "PROMPT_SUFFIXES", _DEFAULT_PROMPT_SUFFIXES)
        suffix = suffixes.get(self.mode, suffixes.get(MODE_USER, ">"))
        fmt = getattr(self.dev, "PROMPT_FORMAT", None)
        if callable(fmt):
            return fmt(self.hostname, self.mode, suffix)
        return f"{self.hostname}{suffix}"

    def banner(self) -> None:
        sys.stdout.write(self.dev.BANNER)
        sys.stdout.flush()

    def auth(self) -> bool:
        """Username/password challenge. v1 accepts any non-empty pair."""
        banner = getattr(self.dev, "AUTH_BANNER", "\nUser Access Verification\n\n")
        # `{hostname}` placeholder lets PAN-OS / FortiOS render their
        # `<host> login:` line.
        user_prompt = getattr(self.dev, "AUTH_USERNAME_PROMPT", "Username: ").replace(
            "{hostname}", self.hostname
        )
        pass_prompt = getattr(self.dev, "AUTH_PASSWORD_PROMPT", "Password: ")
        sys.stdout.write(banner)
        sys.stdout.write(user_prompt)
        sys.stdout.flush()
        try:
            u = sys.stdin.readline()
        except KeyboardInterrupt:
            print(); return False
        if not u or not u.strip():
            print(); return False
        sys.stdout.write(pass_prompt)
        sys.stdout.flush()
        try:
            p = sys.stdin.readline()
        except KeyboardInterrupt:
            print(); return False
        if not p or not p.strip():
            print(); return False
        return True

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        self.banner()
        if not self.auth():
            return
        print()
        while True:
            try:
                line = input(self.prompt())
            except EOFError:
                print(); break
            except KeyboardInterrupt:
                print()
                continue
            line = line.rstrip("\r\n").strip()
            if not line:
                continue
            self.history.append(line)
            try:
                self.execute(line)
            except SystemExit:
                break

    # ------------------------------------------------------------------
    # Command parsing
    # ------------------------------------------------------------------

    def execute(self, line: str) -> None:
        # Split off pipes.
        if "|" in line:
            cmd_part, _, pipes_part = line.partition("|")
            pipes = [p.strip() for p in pipes_part.split("|") if p.strip()]
        else:
            cmd_part, pipes = line, []
        tokens = cmd_part.split()
        if not tokens:
            return
        handler, used = self._resolve(tokens, self.grammar)
        if handler is None:
            return
        if not self._mode_allows(handler):
            print(f"% Command not available in {self.mode} mode.")
            return
        try:
            output = handler["fn"](self, tokens[used:])
        except SystemExit:
            raise
        except Exception as exc:
            print(f"% Internal error: {exc}")
            return
        if output is None or output == "":
            return
        for pipe in pipes:
            output = self._apply_pipe(output, pipe)
            if output is None:
                return
        # Cisco-style: ensure trailing newline but don't double up.
        if not output.endswith("\n"):
            output += "\n"
        sys.stdout.write(output)
        sys.stdout.flush()

    # ------------------------------------------------------------------
    # Prefix-matching command tree walk
    # ------------------------------------------------------------------

    def _resolve(self, tokens: list[str], subtree: dict) -> tuple[Optional[dict], int]:
        i = 0
        node = subtree
        while i < len(tokens):
            tok = tokens[i]
            tok_lc = tok.lower()
            # Case-insensitive prefix match. Real Cisco/IOS-style
            # CLIs and PowerShell are both case-insensitive; the
            # vendor grammars in this repo all use lowercase keys
            # so the lowercased compare is safe.
            candidates = [k for k in node.keys() if isinstance(k, str) and k.lower().startswith(tok_lc)]
            if not candidates:
                print("% Invalid input detected at '^' marker.")
                return None, 0
            if len(candidates) > 1:
                exact = [k for k in candidates if k.lower() == tok_lc]
                if exact:
                    candidates = exact
                else:
                    print(f'% Ambiguous command:  "{tok}"')
                    return None, 0
            key = candidates[0]
            entry = node[key]
            if isinstance(entry, dict) and "fn" in entry:
                return entry, i + 1
            if not isinstance(entry, dict):
                # Defensive — unexpected grammar shape.
                print("% Internal: grammar leaf is not callable.")
                return None, 0
            node = entry
            i += 1
        print("% Incomplete command.")
        return None, 0

    def _mode_allows(self, handler: dict) -> bool:
        required = handler.get("min_mode", MODE_USER)
        try:
            return _MODE_ORDER.index(self.mode) >= _MODE_ORDER.index(required)
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # Pipes
    # ------------------------------------------------------------------

    def _apply_pipe(self, text: str, pipe: str) -> Optional[str]:
        parts = pipe.split(None, 1)
        if not parts:
            return text
        # Pipe operators are case-insensitive (real Cisco/Junos accept
        # `| INCLUDE`, `| Match`, etc.).
        op = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        # Strip trailing newline before processing; we'll add it back.
        lines = text.splitlines()

        # Junos `display` modifier — annotation only (e.g. `| display set`,
        # `| display xml`); the underlying handler already returns the
        # canonical form, so treat as a no-op pass-through.
        if op == "display":
            return text if text.endswith("\n") else text + "\n"

        # Junos `match <regex>` — same semantics as Cisco's `include`.
        if op in ("include", "grep", "match"):
            pat = self._compile(arg)
            if pat is None:
                return None
            out = [l for l in lines if pat.search(l)]
            return ("\n".join(out) + "\n") if out else ""

        if op == "exclude":
            pat = self._compile(arg)
            if pat is None:
                return None
            out = [l for l in lines if not pat.search(l)]
            return ("\n".join(out) + "\n") if out else ""

        if op == "begin":
            pat = self._compile(arg)
            if pat is None:
                return None
            seen = False
            out: list[str] = []
            for l in lines:
                if not seen and pat.search(l):
                    seen = True
                if seen:
                    out.append(l)
            return ("\n".join(out) + "\n") if out else ""

        if op == "section":
            # Cisco: print blocks whose top-level (non-indented) line
            # matches; continue while subsequent lines are indented or
            # bang-only.
            pat = self._compile(arg)
            if pat is None:
                return None
            out = []
            in_section = False
            for l in lines:
                top_level = bool(l) and not l.startswith(" ") and not l.startswith("\t")
                if top_level:
                    in_section = bool(pat.search(l))
                if in_section:
                    out.append(l)
            return ("\n".join(out) + "\n") if out else ""

        if op == "count":
            return f"Number of lines which match regexp = {len(lines)}\n"

        if op in ("more", "no-more"):
            return text + ("\n" if text and not text.endswith("\n") else "")

        print(f"% Unknown pipe operator: {op}")
        return None

    def _compile(self, pattern: str) -> Optional[re.Pattern]:
        try:
            return re.compile(pattern)
        except re.error as exc:
            print(f"% Invalid regex: {exc}")
            return None


def _load_module(path: str):
    spec = importlib.util.spec_from_file_location("device_mod", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load device module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def main() -> None:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: shell.py <device-module.py>\n")
        sys.exit(2)
    mod_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(mod_path):
        sys.stderr.write(f"% device module not found: {mod_path}\n")
        sys.exit(1)
    device = _load_module(mod_path)
    Shell(device).run()


if __name__ == "__main__":
    main()
