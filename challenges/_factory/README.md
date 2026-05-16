# Threat-Hunt Scenario Factory

The factory generates ATT&CK-tactic-aligned threat-hunt challenges
from small YAML configs. It exists because covering every ATT&CK
technique by hand-authoring would be a thousand-hour project; the
factory replaces ~90% of that mechanical work and leaves the human
author free to focus on the storytelling and the IOC weave.

## Layout

```
challenges/_factory/
├── template/                  # Reusable Dockerfile, validator, CLI, entrypoint
│   ├── Dockerfile.in          # `siege/threat-hunt-{slug}:latest`
│   ├── entrypoint.sh
│   ├── validator.py.in        # answers + Flask loopback validator
│   ├── answer                 # CLI dropped into /usr/local/bin/answer
│   └── README.md.in
├── campaigns/                 # One YAML per mini-campaign
│   └── ta0008-lateral-movement.yaml
└── generate.py                # Materialise challenges/<slug>/ from a campaign yaml
```

## Authoring a new mini-campaign

1. Copy `campaigns/_template.yaml` to `campaigns/<tactic-id>-<slug>.yaml`.
2. Fill in the metadata (title, slug, flag, difficulty, points).
3. List the ATT&CK techniques the campaign chains.
4. For each technique, supply:
   * a one-line description of what happens in the synthetic data
   * a question prompt the hunter must answer
   * the canonical answer string the validator scores against
   * the log file + a 1-3 line snippet to seed the generator
5. Run `python3 challenges/_factory/generate.py <campaign-yaml>` to
   materialise `challenges/<slug>/` from the config + templates.
6. `make challenge-images` to bake the image inside DinD.
7. Re-run `scripts/seed_challenges.py` to register the challenge
   with the API.

The generator is deterministic — running it twice on the same yaml
produces the same output. Hand-edits to `challenges/<slug>/` are
safe as long as the yaml stays the source of truth; re-running the
generator overwrites the materialised files.

## What the factory does for you

* Renders the Dockerfile from `Dockerfile.in` with your slug.
* Renders `validator.py` with your question/answer dict baked in.
* Renders `investigation.md` with your prompts.
* Stages the log corpus files you reference (or generates simple
  ones from snippets if `--synthesise` is passed).
* Produces a `challenge.json` manifest with the correct
  `mitre_techniques` list, `docker_image`, `docker_port`, and
  profile.
* Appends a row to `docs/threat-hunt-coverage.md` (idempotent — a
  re-run updates the existing row instead of duplicating).

## What it deliberately doesn't do

* It does not author your log corpus. Synthetic log content is a
  pedagogy decision and the factory just stages files you supply.
* It does not pick technique IDs for you. Authors decide which
  techniques are worth covering in each campaign.
* It does not validate the campaign yaml against the live MITRE
  matrix; technique IDs are author-checked.

## Quality bar

A factory-generated challenge ships when:

1. It builds with `make challenge-images` clean.
2. A scripted happy-path solve produces the flag.
3. Every technique listed in `mitre_techniques` has a
   corresponding artefact in the log corpus the hunter can use.
4. The campaign row in `docs/threat-hunt-coverage.md` is accurate.
