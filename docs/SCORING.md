# Scoring model — EntityGraph Auditor

> **Every score in this application is an internal editorial heuristic.** It is
> not an official Google, Bing, OpenAI, Anthropic, or Perplexity metric, and it
> does not predict rankings, AI citations, or any platform outcome. The exact
> disclaimer string is attached to every scorecard and export.

Scores exist to make editorial judgement *consistent, inspectable and
reproducible* — not to be a truth claim about any search or retrieval system.
All arithmetic runs in Python (`packages/scoring/ega_scoring`), never in a model.

## 1. Component scores (0–10)

Each component is a confidence-aware, 0–10 rating with sub-scores, weights,
`lost_points` ("why points were lost", with counts), rationale, and an
observation count. Insufficient evidence yields `value = null` with
`not_assessed = true` (or `not_applicable = true`) — such components are **never
counted as zero**.

| Key | Name | What it inspects (evidence) |
|---|---|---|
| **EOS** | Entity Optimization | Central entity clarity & salience, supporting entity relevance, attribute/value completeness (EAV), primary-intent coverage, naming consistency, trust entities, page-type fit, semantic coherence (penalises entity stuffing) |
| **ERS** | Entity Relationship | Problem→solution / capability→outcome / process→mechanism→result triples, entity→attribute clarity, cause/effect accuracy (unsupported causal triples are penalised explicitly), claim→evidence connection |
| **KGR** | Knowledge Graph Readiness | Essential triples explicit & accurate, required EAV present, canonical naming/aliases, brand/site consistency, entity-type coherence, proof/source links |
| **FCS** | Fan-Out Coverage | Query coverage across definitional / mechanism / comparison / attribute / use-case / objection queries |
| **PRS** | Passage Retrievability | Answer-first structure, named subject, self-containment, answer-shape match, evidence adjacency, early high-priority info, hierarchy & redundancy |
| **CWS** | Content Weight / Substance | First-party data & information gain, verifiable sourcing, depth beyond restatement, first-hand expertise, claim precision & dating, attribution quality |
| **HRS** | Human Readability | Clarity / plain language, structure & scannability, practical completeness, relevance vs filler, tone & terminology, examples/steps, conversion clarity |

### Sub-score defaults (PRD §9.2)

Each component combines fixed sub-scores with default weights (sum = 100%).
Example — **EOS**: central entity clarity 20, supporting entity relevance 15,
attribute/value completeness 20, primary-intent coverage 15, naming consistency
10, trust/authority entities 10, page-type fit 10. Local-service pages may
reallocate up to 10 points toward local relevance; for non-local page types the
local sub-score is **excluded and weights re-normalised** (never scored 0).

## 2. Fan-Out Coverage — exact arithmetic (PRD §9.4)

```
FCS = 10 × Σ(importance × coverage) / Σ(importance)
```

over **in-scope rows only**. Rows with `scope = OUT_OF_SCOPE` or
`coverage = EXCLUDED` are removed from *both* numerator and denominator.

Coverage weights: `covered = 1.0`, `partial = 0.5`, `missing = 0.0`.
Importance: `3 = core`, `2 = common follow-up`, `1 = edge`.

Provenance is never blended silently: the component records
`observed_queries` vs `simulated_queries`. With zero observed queries the
rationale states that coverage is computed from **simulated queries only
(hypotheses)**.

## 3. Composite (AVR) — profile weights (PRD §9.4)

`AVR = Σ(component × weight)` using the active score profile. Weights are
versioned (`profile` + `profile_version`).

| Profile | EOS | ERS | KGR | FCS | PRS | CWS | HRS |
|---|---|---|---|---|---|---|---|
| informational / glossary | 15 | 15 | 10 | 15 | 15 | 20 | 10 |
| listicle / comparison | 15 | 10 | 15 | 10 | 15 | 20 | 10 |
| commercial (default) | 15 | 15 | 15 | 10 | 15 | 15 | 15 |
| case study | 10 | 15 | 10 | 5 | 10 | 35 | 0 → 15 |

**Missing components:** if a component is `not_assessed`, the composite either
**blocks** (`value = null`) or **re-normalises** the remaining weights with an
explicit note (`renormalized = true`, listing excluded keys). N/A is never a
zero.

## 4. Gate — not averaged away (PRD §9.5)

Gate results (`PASS` / `PASS_WITH_FIXES` / `FAIL` / `NOT_CONFIGURED`) are
**separate from and never averaged into** the composite. A page can score 9.0
and still be `FAIL` — e.g. a fabricated statistic, a canonical brand-fact
contradiction, a banned/forbidden claim, or an unverified regulated
(legal/medical/safety/financial) claim.

- **FAIL** → not publishable as-is. Critical issues are listed *first* in the report.
- **PASS_WITH_FIXES** → publishable after the listed non-critical issues are fixed.
- **NOT_CONFIGURED** → no brand pack; fabrication checks still run.
- **PASS** → no blockers detected.

## 5. Priority (PRD §9.6)

```
Priority = (Impact × Confidence) / Effort
```

`effort` is clamped to ≥ 1. Ordering is `gate_critical desc → priority_score desc
→ severity → effort asc`. The formula is shown to the user, not hidden.

## 6. Determinism & reproducibility

A score set is reproducible from: `content_hash` + page-type/profile version +
context-pack versions + provider/model + prompt versions. Each component carries
its profile version and the report records all of these. Re-running the same
content with the same profile, packs and provider must reproduce the same
numbers (model-derived stage outputs are cached by that key and versioned by the
prompt version).

## 7. Language handling

Readability formulas are language-aware: English (Flesch / Flesch–Kincaid),
French (adapted Flesch, flagged as approximate), and **no English formula for
other scripts** (e.g. Bengali) — those fall back to a qualitative rubric with an
explicit `readability_warning`. English formulas are never applied silently to
non-English content.
