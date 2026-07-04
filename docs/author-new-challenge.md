# Authoring a new challenge

One golden path per challenge style. For the manifest field reference see
[`challenge-spec-v1.md`](challenge-spec-v1.md); for validator options and
best practices see [`author-handbook.md`](author-handbook.md).

Flags and answers are **never** committed. They live in the gitignored
`secrets/` tree and are sealed into per-challenge sidecars at build time
by `scripts/stage-answers.sh` (see the sealing scripts). Author your
manifest with the flag value present locally; the seal step strips it.

## Route A — Tier-1, hand-authored narrative challenge

1. Create `challenges/<slug>/` with a `challenge.json` (or manifest per
   the v1 spec), a `Dockerfile`, and any hand-authored artefacts
   (`logs/`, `pcaps/`, etc.).
2. Choose a validator `type` that matches how the flag is checked
   (`exact`, `regex`, `sigma_rule`, `report_analysis`, …) and put its
   config in the flag entry.
3. Keep the flag value in the local `secrets/` map; `stage-answers.sh`
   copies it to `/opt/flag.txt` inside the image at build time.
4. Validate before committing:
   ```bash
   make test-challenges        # runs every manifest TestCase through the registry
   make dev && make seed       # load into a running stack and solve it by hand
   ```

## Route B — Tier-2, factory mini-campaign

1. Copy `challenges/_factory/template/` and fill in the campaign YAML
   (`_template.yaml`) — narrative, questions, and per-question canonical
   answers.
2. Materialise it with the factory generator:
   ```bash
   python challenges/_factory/generate.py <campaign>
   ```
3. Answers are sealed the same way (`scripts/seal-answers.py` →
   `secrets/answers/campaigns/`); nothing sensitive is committed.

## Per-tier validation checklist

```
[ ] Manifest passes `make test-challenges` (happy-path solve asserted)
[ ] Every flag has at least one pass TestCase and one fail TestCase
[ ] For blue-team hunts: each question's canonical answer is IOC-accurate
[ ] Flag/answer values are only in secrets/ (git grep confirms none tracked)
[ ] Dockerfile builds and the container starts (`build_challenge_images.sh`)
[ ] Description renders cleanly in the catalogue on `make dev`
```

## Validator quick reference

| `type` | Use for |
|---|---|
| `exact` / `regex` | a literal or pattern flag |
| `multi_part` | multi-flag challenges scored per part |
| `sigma_rule` / `yara_rule` | detection-rule authoring challenges |
| `chain_of_custody` / `attack_chain` | ordered evidence / kill-chain |
| `cloud_misconfig` | cloud posture findings |
| `llm_signal` / `prompt_injection_detected` / `jailbreak_attempt` / `agent_abuse_trace` | AI honeypot scenarios |
| `report_analysis` | grading a written incident report against a rubric |
