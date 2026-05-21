#!/usr/bin/env python3
"""Materialise a threat-hunt challenge from a campaign YAML.

Usage:
    python3 challenges/_factory/generate.py challenges/_factory/campaigns/ta0008-lateral-movement.yaml

Reads the campaign config and writes a ready-to-build challenge tree
under ``challenges/<slug>/``. Idempotent — re-running on the same yaml
overwrites the materialised files; hand-edits inside that tree get
clobbered, which is the point: the yaml is the source of truth.

Answers and the reveal flag are not committed in cleartext alongside
the campaign yaml. They live under ``secrets/`` on the operator host
(gitignored). When materialising, generate.py reads the sealed JSON
maps and writes per-challenge ``.answers.json`` and ``.flag.txt``
sidecars next to the Dockerfile. ``scripts/stage-answers.sh`` is the
canonical pre-build hook, but generate.py also writes the sidecars so
the materialised tree is immediately buildable on the operator host.

Deliberately small. No jinja, no click, no yaml lib beyond what
Python ships with the standard ``importlib`` ecosystem (we vendor a
tiny safe-yaml loader for the subset of YAML we use). This keeps
the factory dependency-free so it runs anywhere the repo lives.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "PyYAML is required to run the factory. Install with `pip install pyyaml` "
        "or run inside the api container which already has it.",
        file=sys.stderr,
    )
    sys.exit(1)


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = Path(__file__).resolve().parent / "template"
SECRETS = ROOT / "secrets"


def render_template(text: str, params: dict) -> str:
    """Replace ``{{key}}`` placeholders with values from params.

    Deliberately not a real templating engine — keeps the templates
    debuggable by eye.
    """
    out = text
    for key, value in params.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def normalise_slug(slug: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", slug):
        raise ValueError(f"slug {slug!r} must be kebab-case, 3-64 chars")
    return slug


def load_sealed_answers(campaign_stem: str) -> dict[str, str]:
    """Load ``secrets/answers/campaigns/<campaign-stem>.json`` if present.

    Returns an empty dict on missing/unreadable. Callers fail-loud if
    the result is empty and the yaml also has no per-question answers.
    """
    path = SECRETS / "answers" / "campaigns" / f"{campaign_stem}.json"
    if not path.exists():
        return {}
    with path.open() as fh:
        return json.load(fh) or {}


def load_sealed_flag(slug: str) -> str:
    """Look up the sealed reveal flag for ``slug`` from
    ``secrets/flags.json``. Returns "" if absent.
    """
    path = SECRETS / "flags.json"
    if not path.exists():
        return ""
    with path.open() as fh:
        return (json.load(fh) or {}).get(slug, "")


def build_questions_dict(
    techniques: list[dict], sealed_answers: dict[str, str]
) -> tuple[dict, dict[str, str]]:
    """Turn the campaign's ``techniques`` list into the ordered
    question dict the validator expects, plus the answer map.

    Question IDs are 1-indexed strings to match the player-facing
    ``answer 1`` / ``answer 2`` UX. Per-question ``answer`` is taken
    from ``sealed_answers`` when the yaml has none (post-strip
    state); a yaml-supplied answer overrides the sealed map (useful
    for pre-strip development).
    """
    questions: dict = {}
    answer_map: dict[str, str] = {}
    for idx, tech in enumerate(techniques, start=1):
        qid = str(idx)
        q = tech.get("question") or {}
        prompt = (q.get("prompt") or "").strip()
        hint = (q.get("hint") or "").strip()
        answer = q.get("answer")
        if answer is None:
            answer = sealed_answers.get(qid)
        if not prompt:
            raise ValueError(
                f"technique #{idx} ({tech.get('id')}) is missing prompt"
            )
        if answer is None or answer == "":
            raise ValueError(
                f"technique #{idx} ({tech.get('id')}) has no answer in yaml or "
                f"secrets/answers/campaigns/ — re-run scripts/seal-answers.py "
                f"or hand-edit the sealed map"
            )
        questions[qid] = {
            "prompt": prompt,
            "hint": hint,
            "technique": tech.get("id"),
        }
        answer_map[qid] = str(answer)
    return questions, answer_map


def write_file(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.chmod(path, mode)


def materialise(campaign_path: Path) -> Path:
    with campaign_path.open() as f:
        campaign = yaml.safe_load(f)

    slug = normalise_slug(campaign["slug"])
    target = ROOT / "challenges" / slug

    sealed_answers = load_sealed_answers(campaign_path.stem)
    questions, answer_map = build_questions_dict(
        campaign.get("techniques") or [], sealed_answers
    )
    technique_ids = [t["id"] for t in (campaign.get("techniques") or []) if t.get("id")]

    flag = campaign.get("flag") or load_sealed_flag(slug)
    if not flag:
        raise ValueError(
            f"no flag in yaml and none in secrets/flags.json for slug {slug!r} — "
            f"re-run scripts/seal-flags.py or add a flag to the yaml"
        )

    # --- challenge.json (public manifest — no flag field; the
    # platform reads the flag separately from secrets/flags.json at
    # seed time).
    manifest = {
        "title": campaign["title"],
        "slug": slug,
        "description": campaign["description"].strip(),
        "category": campaign.get("category", "Threat Hunting"),
        "team": campaign.get("team", "blue"),
        "difficulty": int(campaign.get("difficulty", 3)),
        "points": int(campaign.get("points", 350)),
        "hints": [
            {
                "text": "Start with the log file referenced in question 1's hint.",
                "cost": 50,
            }
        ],
        "skills": ["Threat Hunting", "Log Analysis", "MITRE ATT&CK", "Incident Response"],
        "mitre_techniques": technique_ids,
        "docker_image": f"siege/{slug}:latest",
        "docker_port": int(campaign.get("docker_port", 2222)),
        "docker_config": {"profile": campaign.get("profile", "default-strict")},
    }
    write_file(target / "challenge.json", json.dumps(manifest, indent=2) + "\n")

    # --- Dockerfile (verbatim from template)
    write_file(target / "Dockerfile", (TEMPLATE / "Dockerfile.in").read_text())

    # --- entrypoint.sh (verbatim, executable)
    write_file(
        target / "entrypoint.sh",
        (TEMPLATE / "entrypoint.sh").read_text(),
        mode=0o755,
    )

    # --- answer CLI (verbatim, executable)
    write_file(
        target / "answer",
        (TEMPLATE / "answer").read_text(),
        mode=0o755,
    )

    # --- validator.py (no answer keys, no cleartext flag)
    validator_src = render_template(
        (TEMPLATE / "validator.py.in").read_text(),
        {
            "title": campaign["title"],
            "slug": slug,
            "questions_json": json.dumps(questions, indent=4),
        },
    )
    write_file(target / "validator.py", validator_src)

    # --- sealed sidecars (gitignored; copied into the container at
    # build time, mode 0600 root-owned inside the image)
    write_file(target / ".answers.json", json.dumps(answer_map, indent=2) + "\n", mode=0o600)
    write_file(target / ".flag.txt", flag.strip() + "\n", mode=0o600)

    # --- investigation.md
    md = [f"# Investigation Briefing — {campaign['title']}", ""]
    md.append(campaign["description"].strip())
    md.append("")
    md.append("## You have")
    md.append("")
    md.append("```")
    for fname in (campaign.get("logs") or {}):
        md.append(f"~/logs/{fname}")
    md.append("```")
    md.append("")
    md.append("## You need to answer")
    md.append("")
    for qid, q in questions.items():
        md.append(f"{qid}. **{q['prompt']}**")
        md.append(f"   _hint: {q['hint']}_")
        md.append("")
    md.append("## Submitting answers")
    md.append("")
    md.append("```sh")
    md.append("answer                          # list open questions")
    md.append('answer 1 "<value>"              # single-shot validate')
    md.append('answer remember 1 "<value>"     # remember locally')
    md.append("answer reveal                   # reveal flag when all correct")
    md.append("```")
    md.append("")
    md.append("## ATT&CK techniques chained")
    md.append("")
    for tech in campaign.get("techniques") or []:
        desc = (tech.get("description") or "").strip().replace("\n", " ")
        md.append(f"* `{tech.get('id')}` — {desc}")
    md.append("")
    write_file(target / "investigation.md", "\n".join(md))

    # --- log corpus
    for fname, body in (campaign.get("logs") or {}).items():
        write_file(target / "logs" / fname, body if body.endswith("\n") else body + "\n")

    return target


def main():
    if len(sys.argv) != 2:
        print("usage: generate.py <campaign-yaml>", file=sys.stderr)
        sys.exit(2)
    out = materialise(Path(sys.argv[1]))
    print(f"materialised: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
