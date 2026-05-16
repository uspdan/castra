#!/usr/bin/env python3
"""Materialise a threat-hunt challenge from a campaign YAML.

Usage:
    python3 challenges/_factory/generate.py challenges/_factory/campaigns/ta0008-lateral-movement.yaml

Reads the campaign config and writes a ready-to-build challenge tree
under ``challenges/<slug>/``. Idempotent — re-running on the same yaml
overwrites the materialised files; hand-edits inside that tree get
clobbered, which is the point: the yaml is the source of truth.

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


def build_questions_dict(techniques: list[dict]) -> dict:
    """Turn the campaign's ``techniques`` list into the ordered
    question dict the validator expects.

    Question IDs are 1-indexed strings to match the player-facing
    ``answer 1`` / ``answer 2`` UX.
    """
    out = {}
    for idx, tech in enumerate(techniques, start=1):
        q = tech.get("question") or {}
        prompt = (q.get("prompt") or "").strip()
        hint = (q.get("hint") or "").strip()
        answer = q.get("answer")
        if not prompt or answer is None:
            raise ValueError(
                f"technique #{idx} ({tech.get('id')}) is missing prompt or answer"
            )
        out[str(idx)] = {
            "prompt": prompt,
            "hint": hint,
            "answer": str(answer),
            "technique": tech.get("id"),
        }
    return out


def write_file(path: Path, content: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.chmod(path, mode)


def materialise(campaign_path: Path) -> Path:
    with campaign_path.open() as f:
        campaign = yaml.safe_load(f)

    slug = normalise_slug(campaign["slug"])
    target = ROOT / "challenges" / slug

    questions = build_questions_dict(campaign.get("techniques") or [])
    technique_ids = [t["id"] for t in (campaign.get("techniques") or []) if t.get("id")]

    # --- challenge.json
    manifest = {
        "title": campaign["title"],
        "slug": slug,
        "description": campaign["description"].strip(),
        "category": campaign.get("category", "Threat Hunting"),
        "team": campaign.get("team", "blue"),
        "difficulty": int(campaign.get("difficulty", 3)),
        "points": int(campaign.get("points", 350)),
        "flag": campaign["flag"],
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

    # --- validator.py
    validator_src = render_template(
        (TEMPLATE / "validator.py.in").read_text(),
        {
            "title": campaign["title"],
            "slug": slug,
            "flag": campaign["flag"],
            "questions_json": json.dumps(questions, indent=4),
        },
    )
    write_file(target / "validator.py", validator_src)

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
