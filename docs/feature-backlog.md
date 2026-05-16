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

## (template for future entries)

**Source:** _who/when/context_

**Pitch:** _one paragraph_

**Why it's interesting:**

* _bullet_
* _bullet_

**Architectural options:** _table or list_

**Open questions:** _bullets_
