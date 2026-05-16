# Feature Backlog

Larger ideas captured for later, surfaced by the user during build
sessions. Not yet scheduled; not yet refined. Each entry includes
enough context to pick up cold.

---

## report-analysis — player writes a post-hunt incident report; system scores it

**Source:** user message, 2026-05-16 mid-session during the threat-
hunt factory build-out.

**Pitch:** Real IR work doesn't end with "I found the IOC". It ends
with a written report. After a player completes a threat-hunt
challenge, give them an `incident-report.md` template inside the
container and a `submit-report` CLI. The platform analyses the
report for accuracy, completeness, and clarity, returns a graded
critique alongside (or in place of) the flag.

**Why it's interesting:**

* Closes the loop on the "from triage to writeup" workflow that
  every real SOC / IR analyst lives in. Today the platform stops
  at "find the IOC".
* Forces players to articulate *why* something is malicious, not
  just *that* it is. Vastly more pedagogical than fact-finding.
* Differentiates Siege Range from every other CTF — most fail at
  this exact transition.

**Two architectural options:**

| Option | How it scores | Determinism | Build cost |
|---|---|---|---|
| Rule-based | Required-keyword inclusion check (must mention all the canonical IOCs, the MITRE technique IDs, the affected host, the timeline) + simple heuristics for structure (does it have a summary / timeline / IOCs / containment sections?) | Fully deterministic | Low — ~1 day |
| LLM-rubric | Send the report + canonical-answer set + rubric to the platform's reference LLM container (already exists from Sprint 11). LLM returns structured JSON: `{accuracy: 0-10, completeness: 0-10, clarity: 0-10, missing_iocs: […], strengths: […], suggestions: […]}`. Flag drops on a threshold score. | Non-deterministic | Medium — ~3 days |
| Hybrid (recommended) | Rule-based gate (must mention every canonical IOC + every technique ID) + LLM qualitative critique. Flag drops on the rule-based gate; the LLM feedback is non-blocking critique a player can iterate on. | Gated correctness is deterministic; critique is advisory | Medium |

**Integration with the existing factory:**

The campaign YAML already has the canonical answers. Add a
`report_rubric:` section that lists:

* `must_mention_iocs:` — list of strings/regexes the report has to contain
* `must_cite_techniques:` — ATT&CK IDs the report has to reference
* `sections_required:` — `[summary, timeline, iocs, containment, recommendations]`
* `llm_rubric_prompt:` — free-text rubric for the LLM critique pass

The validator backend already runs in-container; extend it with a
`/submit-report` endpoint. The `submit-report` CLI tool wraps it.

**Open questions:**

* Should the flag drop on the technical hunt (current state) *or*
  the report (more pedagogical)? Probably keep both — the hunt
  gives a small flag, the report gives the headline points.
* Where does the LLM live? In-container (heavy) or call out to
  the platform's reference LLM container (already wired)?
* Privacy: the report is the player's work. Don't ship it
  off-platform without consent.

---

## author-and-operator-onboarding — better docs on test connect, scaffolding, deploy, update

**Source:** user message, 2026-05-16 late in the threat-hunt build session.

**Pitch:** Today the docs are scattered. To bring up the stack you
need pieces of `README.md`, `WORK_PLAN.md`, the operator handbook,
the threat-hunt-factory README, and tribal knowledge from the
commit log. Land four shorter docs that a new author/operator
can read in order:

1. `docs/connect.md` — how to reach every layer that a hunter,
   author, or operator might need: the public UI, the API,
   the SSH challenge ports, the API container shell, the DinD
   docker daemon, the postgres console, the redis console. With
   exact commands for each, plus a "ports map" diagram.

2. `docs/author-new-challenge.md` — single golden path for
   authoring a new challenge from scratch. Covers both the
   factory route (Tier 2 mini-campaign) and the hand-authored
   route (Tier 1 narrative). Includes per-tier validation
   checklist (happy-path solve + per-question IOC accuracy).

3. `docs/deploy.md` — three flavours: local dev (`make dev`),
   staging (`make prod` + the production overrides), and a
   real internet-exposed deploy (TLS certs, DNS, env vars,
   first-time-setup, OTel collector wiring, backup retention).
   Currently scattered across `docs/runbooks/`, the operator
   handbook, and the deploy script.

4. `docs/update.md` — what an operator runs when a new
   release lands: pull, run pending DB migrations, rebuild
   challenge images, smoke-test, roll forward. Includes a
   rollback procedure (which lives in
   `docs/runbooks/rollback.md` today but isn't referenced
   from anywhere else).

**Why it's interesting:**

* Lowers the bar to contribute. Right now authoring a new
  threat-hunt challenge means reading 3-4 files plus copy-
  pasting from the existing ones.
* Reduces the cost of every future build session. Sprint 13
  burnt a lot of time discovering how the stack fit together;
  the next person shouldn't have to.
* Operator-side: someone running this in production needs
  to be able to triage without grepping the codebase.

**Open questions:**

* Should `docs/connect.md` literally include passwords and
  bearer tokens? Probably env-var refs only.
* `docs/deploy.md` overlaps with the existing operator
  handbook — consolidate or cross-link?
* Should there be a generated index page that surfaces every
  doc in one place, or just a top-level `docs/README.md`?

---

## (template for future entries)

**Source:** _who/when/context_

**Pitch:** _one paragraph_

**Why it's interesting:**

* _bullet_
* _bullet_

**Architectural options:** _table or list_

**Open questions:** _bullets_
