#!/usr/bin/env python3
"""seal-answers — move cleartext answers out of the public source.

Two surfaces today:

1. Threat-hunt factory campaigns:
   ``challenges/_factory/campaigns/<slug>.yaml`` has every
   technique's ``question.answer`` field in cleartext. Strip them
   into ``secrets/answers/campaigns/<slug>.json`` (gitignored).

2. Live-shell challenge validators:
   ``challenges/<slug>/validator.py`` (factory-emitted and
   hand-authored alike) bakes a ``QUESTIONS = {...}`` dict where
   each entry carries ``answer``. Strip into
   ``secrets/answers/validators/<slug>.json`` and rewrite the
   validator to load answers from ``/opt/answers.json`` at start.

Idempotent. Re-running re-extracts whatever's currently in the
public files; if you accidentally regenerate a validator with
the old pattern, run this and commit.

Usage:
    scripts/seal-answers.py            # strip + write to secrets/
    scripts/seal-answers.py --dry-run

The Dockerfiles still need to COPY the answers sidecar at build
time — handled by ``scripts/stage-answers.sh`` which the build
pipeline calls before each ``docker build``.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHALLENGES_DIR = ROOT / "challenges"
CAMPAIGNS_DIR = CHALLENGES_DIR / "_factory" / "campaigns"
SECRETS_DIR = ROOT / "secrets" / "answers"


# ---------------------------------------------------------------------------
# Campaign YAML — strip the ``answer`` field from every technique
# ---------------------------------------------------------------------------

def _strip_campaign_yaml(text: str) -> tuple[str, dict]:
    """Walk the campaign YAML line by line, extract every
    ``answer: "..."`` value (numbered by appearance order matching
    the technique index), and rewrite the YAML with the answer
    fields removed.

    YAML structure we're matching (indentation matters):

        techniques:
          - id: T1078
            ...
            question:
              prompt: |
                ...
              hint: |
                ...
              answer: "REDACTED"

    Hand-rolled — keeps the existing yaml indentation untouched.
    A real yaml-roundtrip would normalise quoting/spacing and
    create a noisy diff; this surgically removes one line per
    technique.
    """
    out_lines: list[str] = []
    answers: dict[str, str] = {}
    qid = 0
    pat = re.compile(r"^(\s+)answer:\s*(.+?)\s*$")
    for line in text.splitlines(keepends=True):
        m = pat.match(line)
        if m is not None:
            qid += 1
            raw_val = m.group(2).strip()
            # Strip surrounding quotes if present.
            if (raw_val.startswith('"') and raw_val.endswith('"')) or \
               (raw_val.startswith("'") and raw_val.endswith("'")):
                raw_val = raw_val[1:-1]
            answers[str(qid)] = raw_val
            # Skip — don't emit this line.
            continue
        out_lines.append(line)
    return "".join(out_lines), answers


# ---------------------------------------------------------------------------
# Validator.py — strip every ``"answer": "..."`` inside the
# ``QUESTIONS = {...}`` dict literal.
# ---------------------------------------------------------------------------

_VALIDATOR_LOADER_BLOCK = '''\
# Answers are not committed to the public source. The challenge
# container's Dockerfile copies ``secrets/answers/validators/<slug>.json``
# (gitignored) to ``/opt/answers.json`` at build time, and the
# loader below merges them into QUESTIONS before the validator
# starts serving.
import json as _json
import os as _os

_ANSWERS_PATH = _os.environ.get("SIEGE_ANSWERS_PATH", "/opt/answers.json")
try:
    with open(_ANSWERS_PATH) as _fh:
        _SEALED_ANSWERS = _json.load(_fh)
except FileNotFoundError:
    _SEALED_ANSWERS = {}

for _qid, _val in (_SEALED_ANSWERS or {}).items():
    if _qid in QUESTIONS:
        QUESTIONS[_qid]["answer"] = _val
'''


def _strip_validator(text: str, slug: str) -> tuple[str, dict] | None:
    """Find the module-level ``QUESTIONS = {...}`` literal, extract
    every ``"answer": "..."`` value into a dict, and rewrite the
    source so each QUESTIONS entry has the ``answer`` key removed
    (or set to an empty placeholder) and a loader block appended
    that fills them in from ``/opt/answers.json`` at runtime.

    Returns ``None`` if the file doesn't have a recognisable
    QUESTIONS literal — leaves it untouched.
    """
    tree = ast.parse(text)
    questions_node = None
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "QUESTIONS"
            and isinstance(node.value, ast.Dict)
        ):
            questions_node = node
            break
    if questions_node is None:
        return None

    # Map qid (str) -> answer (str) by walking the dict literal.
    answers: dict[str, str] = {}
    dict_lit = questions_node.value
    for key_node, val_node in zip(dict_lit.keys, dict_lit.values):
        if not isinstance(key_node, ast.Constant):
            continue
        qid = str(key_node.value)
        if not isinstance(val_node, ast.Dict):
            continue
        for k2, v2 in zip(val_node.keys, val_node.values):
            if isinstance(k2, ast.Constant) and k2.value == "answer" and isinstance(v2, ast.Constant):
                answers[qid] = str(v2.value)

    if not answers:
        return None  # nothing to strip — already stripped

    # Line-based rewrite: replace every ``"answer": "..."`` line
    # whose key is exactly "answer" with nothing, and append the
    # loader block at the end of the QUESTIONS literal.
    out_lines: list[str] = []
    pat = re.compile(r'^(\s*)"answer"\s*:\s*[^,]+,?\s*$')
    for line in text.splitlines(keepends=True):
        if pat.match(line):
            continue
        out_lines.append(line)
    rewritten = "".join(out_lines)

    # Append loader block after the QUESTIONS dict.
    # End-of-dict marker: the closing `}` followed by a blank line.
    # Insert the loader block right after the QUESTIONS assignment.
    end_lineno = questions_node.end_lineno or len(rewritten.splitlines())
    # Reconstruct with the loader inserted after end_lineno of the
    # REWRITTEN (answer-line-stripped) source. Because we only
    # deleted lines, line numbers shifted: count how many answer
    # lines fell before the original end_lineno.
    deletions_before_end = sum(
        1 for i, line in enumerate(text.splitlines())
        if i < end_lineno and pat.match(line + "\n")
    )
    new_end_lineno = end_lineno - deletions_before_end

    new_lines = rewritten.splitlines(keepends=True)
    insert_at = new_end_lineno
    new_lines.insert(insert_at, "\n\n" + _VALIDATOR_LOADER_BLOCK + "\n")

    return "".join(new_lines), answers


def _ensure_dirs(args) -> None:
    if args.dry_run:
        return
    (SECRETS_DIR / "campaigns").mkdir(parents=True, exist_ok=True)
    (SECRETS_DIR / "validators").mkdir(parents=True, exist_ok=True)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    _ensure_dirs(args)

    # --- campaigns ---
    campaign_total = 0
    campaign_stripped = 0
    if CAMPAIGNS_DIR.is_dir():
        for yaml_path in sorted(CAMPAIGNS_DIR.glob("*.yaml")):
            if yaml_path.name.startswith("_"):
                continue
            campaign_total += 1
            text = yaml_path.read_text()
            new_text, answers = _strip_campaign_yaml(text)
            if not answers:
                continue
            slug = yaml_path.stem
            if not args.dry_run:
                yaml_path.write_text(new_text)
                out = SECRETS_DIR / "campaigns" / f"{slug}.json"
                out.write_text(json.dumps(answers, indent=2, sort_keys=True) + "\n")
                os.chmod(out, 0o600)
            campaign_stripped += 1

    # --- validators ---
    validator_total = 0
    validator_stripped = 0
    for v_path in sorted(CHALLENGES_DIR.rglob("validator.py")):
        if "_factory" in v_path.parts:
            continue
        validator_total += 1
        text = v_path.read_text()
        slug = v_path.parent.name
        res = _strip_validator(text, slug)
        if res is None:
            continue
        new_text, answers = res
        if not args.dry_run:
            v_path.write_text(new_text)
            out = SECRETS_DIR / "validators" / f"{slug}.json"
            out.write_text(json.dumps(answers, indent=2, sort_keys=True) + "\n")
            os.chmod(out, 0o600)
        validator_stripped += 1

    tag = "(dry run) " if args.dry_run else ""
    print(f"{tag}campaigns: stripped {campaign_stripped} / {campaign_total}")
    print(f"{tag}validators: stripped {validator_stripped} / {validator_total}")
    if not args.dry_run:
        print(f"answers written under {SECRETS_DIR.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
