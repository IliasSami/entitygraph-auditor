# Aentio — UX/UI Design Spec + Google Stitch Prompt Pack

**Tagline:** Make any page clear, credible, and citable — for people, search engines, and AI answers.
**Type:** Self-hosted · open source · free content optimizer for AI search visibility, AEO, GEO, and entity optimization, grounded in the business's own knowledge graph.

**How to use this file**
- **Part A** is the full design spec. Give it to any agentic designer (Stitch, v0, Figma Make, Lovable), or use it as the source of truth for the build.
- **Part B** is the Stitch prompt pack. Paste the prompts **in order, one per generation**, into the same Stitch project. Prompt 1 sets the design system and every later prompt inherits it.
- **Part C** lists the refinement micro-prompts and what changed from the earlier version.

---

# PART A — DESIGN SPEC

## A1. Product thesis

Surfer, Frase, and NeuronWriter all answer one question: *"Does my page look like the pages already ranking?"* That made sense for ten blue links. It does not hold for AI answers.

AI engines retrieve **passages**, resolve **entities**, prefer **verifiable facts**, and reward **information the other sources don't have**. Aentio answers a different question:

> **"If an AI engine read this page, could it understand who we are, extract a correct answer, trust it, and cite us?"**

What Aentio takes from each tool:

| Borrowed from | Best practice | Aentio version |
|---|---|---|
| Surfer | Live editor with side-panel guidance | Same pattern, but the guidance is explained, actionable cards, not a keyword checklist |
| Surfer / NeuronWriter | Choose which competitors to compare against and exclude outliers | Competitor selection with auto-exclusion reasons ("forum thread — different format") |
| NeuronWriter | Term targets split by placement (title / H1 / H2 / body) | Entity targets by placement, shown as **ranges**, never exact counts |
| NeuronWriter | Entity-flavoured NLP terms | Typed entities (Organization, Service, Concept, Place) linked to the business knowledge graph and to Wikidata |
| Frase | Research-first workflow, question mining, drag-and-drop outline builder | A Brief Builder with a source pool → outline → writer handoff |
| Frase | Search Console content-decay view | Library with freshness and decay plus **fact-change propagation** |
| All three | Content audit of existing URLs | Import an existing URL, sitemap, or WordPress site and optimize in place |

What none of them have, and Aentio adds:
1. **An Entity Hub (business knowledge graph)**, used as the source of truth for every claim.
2. **A passage map**: each section is scored as a standalone chunk an AI engine might quote.
3. **A claims ledger**: every factual claim is linked to a verified fact or source, and contradictions with the Entity Hub are flagged.
4. **An originality (information gain) check**: what this page says that the top results don't.
5. **AI Visibility tracking with honest methodology**: sampled runs, variance, and engines the user configured.
6. **Agent edits as tracked changes**: nothing is written without approval.
7. **Schema generated from the graph**: consistent `@id` and `sameAs` links across the whole site.

## A2. Users and jobs-to-be-done

| User | Main job | Design implication |
|---|---|---|
| SEO consultant / agency | Optimize many client pages quickly and prove the value | Multiple workspaces (one per client), exportable reports, bulk audit |
| Content writer | Write a strong draft without learning SEO | Calm editor, plain-English cards, a brief handed to them |
| Content strategist | Plan clusters and briefs | Brief Builder, Library clusters |
| Technical SEO | Schema, entity consistency, deployment | Schema graph, JSON-LD, Git/WordPress export, self-host status |
| Small business owner | "Make my page show up in ChatGPT" | Guided wizard, readiness labels instead of jargon, one obvious next step |

## A3. UX principles

1. **One job per screen.** Research, write, govern entities, track, and publish each have their own space.
2. **No vanity score.** The lead is a readiness label ("Almost ready — 3 blockers"). The number is secondary and marked as directional.
3. **Every recommendation explains itself.** Each one carries what, why, impact, confidence, and a preview, then Apply / Edit / Dismiss.
4. **Approve, don't auto-write.** Agent output always arrives as tracked changes.
5. **The business is the source of truth.** Facts come from the Entity Hub, not from model memory.
6. **Progressive disclosure.** Summary first, then detail, then raw data such as competitor tables or JSON-LD.
7. **Never use colour alone.** Every highlight also has an underline style and a gutter glyph.
8. **Keyboard-first for power users.** ⌘K command palette, J/K to move between suggestions, A to accept, D to dismiss.
9. **Make self-hosting visible.** Which model, where data lives, token usage, and backups are always one glance away.
10. **Calm density.** Compact (8px grid, 32px table rows), but generous around the writing surface.

## A4. Scoring model (replaces "Content Score")

**Answer Readiness** has five dimensions. Each shows a band: Strong (green) / Fair (amber) / Weak (red).

| Dimension | Plain-English question | Signals |
|---|---|---|
| **Entities** | Does the page clearly name who, what, and where? | Required entities covered; ambiguous pronouns; brand named in key passages; links to the knowledge graph |
| **Answers** | Can someone get the answer in 2 sentences? | Direct answer early; question coverage; definitions; comparisons; steps |
| **Evidence** | Can every important claim be checked? | Claims linked to verified facts or sources; contradictions; stats with dates |
| **Passages** | Would each section still make sense if quoted alone? | Section length (roughly 40–300 words), answer-first sentence, self-contained subject, heading phrased as a question or topic |
| **Originality** | What do we say that others don't? | Overlap with top results; first-party data, examples, opinions, process |

- **Overall** = a label ("Ready" / "Almost ready" / "Needs work") plus a blocker count.
- A small tabular number (for example 72) has the tooltip *"Directional. Not a ranking prediction."*
- **Blockers** are High-impact issues: a fact contradiction, no direct answer, or a missing core entity.

## A5. Information architecture

**Global:** a top bar with the workspace (client) switcher, ⌘K search, an Agent activity indicator, a self-host status dot, and the user menu.

**Sidebar** (240px, collapses to a 56px icon rail):
1. **Home** — the attention queue
2. **Optimize** — new optimization and recent documents
3. **Briefs**
4. **Library** — pages, clusters, audits
5. **Entity Hub**
6. **AI Visibility**
7. *(separator)* **Settings** — models, data sources, integrations, team, privacy

**Document workspace:** context panel on the left (280px, collapsible), editor in the centre (max 720px reading width), Intelligence panel on the right (380px) with a vertical icon tab rail.

## A6. Core flows

1. **New page:** Topic & intent → Business context (pick entities) → Research (choose competitors, read the AI answer landscape) → Brief → Draft → Optimize → Publish.
2. **Existing page:** Library → Import URL → Auto-audit → Optimizer opens with issues pre-loaded.
3. **Agent pass:** Run agent (choose scope: whole page / selection / one dimension) → plan shown → tracked changes → accept or reject → re-score.
4. **Fact change:** Update a fact in the Entity Hub → "Used on 7 pages" → bulk-review the affected passages.
5. **AI visibility loop:** Prompt shows the brand Absent → Missing attributes → "Fix in optimizer" opens the relevant page with a recommendation pinned.

## A7. Screens

### 1. Content Optimizer (hero)

**Header bar:** breadcrumb (Library / Agency bookkeeping), a "Draft" status pill, the model badge "Local · Ollama", presence avatars, and the buttons Run agent (primary) and Publish.

**Left — Context panel** (collapsible sections):
- Target query and intent chip
- Page type, audience, region, tone
- Business entities in use (typed chips)
- Approved facts (each with a check mark and verified date)
- Competitors (7 included / 3 excluded) and an AI answer reference

**Centre — Editor:**
- Serif reading font for content, with an H1/H2 outline in the bottom bar.
- **Highlight layers toggle** in the toolbar: Entities · Claims · Answers · Issues.

| Highlight | Underline style | Gutter glyph |
|---|---|---|
| Missing or ambiguous entity | Amber dashed | ◆ |
| Claim needs a source / conflicts | Blue dotted (red if it conflicts) | § |
| Strong direct answer | Green left bar | ✓ |
| Vague or filler | Red wavy | ! |

- The **passage gutter** carries a small band dot per H2 section. Hovering it shows that passage's mini-score.
- **Selection toolbar:** Make answer-first · Name the entity · Add source · Add FAQ · Simplify · Explain.
- **Bottom bar:** words, reading time, readability grade, outline toggle, "Saved locally".

**Right — Intelligence panel** (vertical tabs: Overview · Entities · Answers · Evidence · Passages · Structure):

- **Overview:** readiness label, blocker count, five dimension bars, and the top 3 recommendation cards.
- **Entities:**
  - Grouped into "From your business" (Entity Hub) and "From top results".
  - Each chip shows type, status (Covered / Weak / Missing), and placement guidance as ranges ("Body 2–4 · in an H2").
  - Button: "Add from Entity Hub".
- **Answers:**
  - Questions (from People Also Ask, AI answers, and the brief) with Answered / Partial / Missing status.
  - "Answer block" templates: definition, steps, comparison table, pricing, pros and cons.
  - Prompt coverage for this page from AI Visibility.
- **Evidence:** the claims ledger, in rows of `claim → linked fact or source → status (Verified / Unsourced / Conflict)`, plus an Originality meter: "Unique vs top 7: 34%".
- **Passages:** a list of sections with length, self-containment, answer-first status, and the entity named.
- **Structure:** heading hierarchy, internal link suggestions (from the Library), schema to generate, and FAQ/table opportunities.

**Recommendation card anatomy:**
- Title (an imperative verb).
- One-line reason that names the real problem in the text.
- Impact pill: High / Med / Low.
- Confidence shown as 3 dots.
- Dimension tag.
- Expandable before/after preview.
- Buttons: **Apply**, Edit, Explain, Dismiss (with an optional reason).

### 2. Optimizer — Agent review state
- The right panel becomes **Agent run**:
  - Plan checklist: Read draft ✓, Compared 7 sources ✓, Checked 14 claims against Entity Hub ✓, Proposed 6 edits.
  - Footer: "Local model · 18.2k tokens · 41s".
- The editor shows **tracked changes**, with insertions underlined in indigo and deletions struck through. Each hunk has inline ✓ / ✕ buttons.
- **Sticky review bar:** "6 suggestions · J/K to move · A accept · D dismiss · Accept all in Answers".
- Nothing is saved to the document until it is accepted.

### 3. Home (dashboard)
- Greeting plus one sentence: "4 pages need attention · 1 fact change affects 7 pages".
- **Attention queue** (the main element). Each row shows the page, the reason pill, impact, and an Open button.
  - Reasons: Fact conflict, Lost AI mention, Weak direct answer, Missing entity, Stale (180d+).
- **Four compact metric tiles**, each with a one-line definition and a 30-day sparkline: Pages ready, Entity consistency, AI mention rate, Freshness.
- **"Recent fact changes"** card showing the affected pages.
- Quick actions: Optimize a page, Import URL, Create brief, Track prompts.
- A small activity feed.

### 4. New Optimization wizard
Four steps with a skippable stepper:
1. **Topic & intent:** query, auto-detected intent with an option to override, page type, audience, region, language, tone.
2. **Business context:** pick entities from the Entity Hub (searchable typed chips), proof points, and sources.
3. **Research:**
   - Left: **SERP competitors table** with an include toggle, rank, domain, format, words, entity overlap, and an auto-exclude reason.
   - Right: **AI answer landscape**, showing what current AI answers say, the sources they cite, and the attributes they cover.
   - Below: the questions found.
4. **Brief & draft:** go to the Brief Builder, or "Import existing draft".

### 5. Brief Builder
- **Left: source pool** (tabs: Competitor headings · Questions · Entity Hub facts · AI answer attributes). Items can be dragged.
- **Centre: outline.** Each section card has:
  - Heading.
  - Purpose (answer / explain / compare / prove).
  - Target entities.
  - Required facts.
  - Answer-first stub.
  - Word range.
- **Right:** brief settings, writer notes, and exports (Markdown, PDF, share read-only link, "Send to editor").

### 6. Entity Hub
- **List view** by default. It suits governance work better than a graph canvas.
  - Filters by type.
  - Columns: name, type, used-on count, facts, last verified, health.
- **Graph view** toggle shows the relationship map.
- **Detail drawer:**
  - Canonical name, aliases, type, one-sentence definition (≤160 characters).
  - `sameAs` links (Wikidata, LinkedIn, Google Business Profile, Crunchbase).
  - `@id` URI.
  - Verified facts table: fact, value, source, verified date, owner.
  - Relationships (offers / located in / serves / founded by / competes with).
  - Schema type.
  - Usage: "Mentioned on 12 pages · Missing from 3 priority pages · 1 conflict".
- **Import:** crawl site, existing schema, CSV, Wikidata lookup.

### 7. AI Visibility
- **Prompt sets** (clusters) shown as tabs.
- **Table columns:** prompt, engines, mention rate ("3/5 runs"), status (Cited / Mentioned / Absent), our URL cited, competitors cited, 30-day trend, last run.
- **Detail panel:**
  - Answer snapshot with brand and competitor mentions highlighted.
  - Sources cited.
  - Missing attributes checklist (definition, pricing, comparison, process, proof, limitations).
  - Buttons: Fix in optimizer, Create brief.
- **Methodology footer, always visible:** *"5 sampled runs per engine · Oct 14, 2026 · AI answers vary — treat as directional."* Engines without an API are marked "Manual snapshot".

### 8. Publish & Schema
- **Pre-publish checklist gate:** "2 blockers · 3 warnings", with "Fix" or "Publish anyway (logged)".
- **Previews:** search result, social card, and **AI answer preview** (the passage most likely to be quoted).
- **Schema graph:** toggles for Article, FAQPage, Service, Organization, BreadcrumbList, all built from the Entity Hub with shared `@id`. JSON-LD in monospace with a "Valid" status.
- **Destinations:** WordPress (REST), Markdown, HTML, Git commit (static sites), JSON-LD, CSV entity report.
- **Self-host status card:** model, storage path, tokens this month, last backup.

### 9. Library / Audit
- Table of pages: title/URL, cluster, readiness band, entity consistency, AI mentions, last updated, traffic trend (if Search Console is connected), owner, status.
- Filter pills and saved views.
- Bulk actions: Audit, Re-check facts, Export report.
- Import options: URL, sitemap, WordPress, CSV.

### 10. Setup and Settings (self-host)
- **First-run wizard:**
  1. Workspace and business basics.
  2. **AI model:**
     - Local (Ollama), OpenAI-compatible endpoint, or a hosted provider with the user's own key.
     - "Test connection" button.
     - A privacy note per option.
  3. **Search data:** bring your own SERP API key, or manual import.
  4. Import entities.
  5. Privacy: telemetry **off** by default, data location shown.
- **Settings:** the same areas plus team roles, backups, and exports (everything exportable as JSON).

## A8. Agent interaction model
- **Scopes:** whole page · selection · one dimension · one recommendation.
- **Always show:** the plan, sources read, facts checked, and model, token, and time.
- **Output is always tracked changes or proposal cards.** The agent never edits silently.
- **Facts the agent uses** must come from the Entity Hub or a cited source. Unverifiable claims are proposed as "Needs source", not invented.
- **Stop / pause** is always visible while the agent is running.

## A9. Design system tokens

**Typography**
- UI: **Inter**, 13/14/16 body, 20/24/32 headings, tabular numerals for all metrics.
- Editor content: **Source Serif 4**, 18px, line-height 1.65.
- Code and JSON-LD: **JetBrains Mono**, 13px.

**Colour (light)**

| Role | Value |
|---|---|
| Background | `#FAFAF9` |
| Surface | `#FFFFFF` |
| Subtle surface | `#F5F5F4` |
| Border | `#E7E5E4` |
| Text | `#1C1917` |
| Muted text | `#78716C` |
| Primary | `#4338CA` (indigo) · hover `#3730A3` · soft `#EEF2FF` |
| Success | `#15803D` / soft `#F0FDF4` |
| Warning | `#B45309` / soft `#FFFBEB` |
| Danger | `#B91C1C` / soft `#FEF2F2` |
| Info / claims | `#1D4ED8` / soft `#EFF6FF` |

**Colour (dark):** background `#0C0C0E`, surface `#16161A`, border `#27272A`, text `#FAFAFA`, muted `#A1A1AA`, primary `#818CF8`. Semantic colours shift one step lighter.

**Shape and density**
- Radius: 8px for inputs and buttons, 12px for cards, 999px for pills.
- 1px borders. Shadows only on overlays (drawers, popovers, the toolbar).
- 8px spacing scale.
- Button height 32px (compact) and 36px (default).
- Table row 36px.
- Sidebar 240px; context panel 280px; intelligence panel 380px; editor 720px maximum.

**Icons:** Lucide-style, 16px, 1.5px stroke, used sparingly.

**Motion:** 150–200ms ease-out. Panels slide; nothing bounces.

## A10. States, responsive, accessibility

**States:**
- Every screen needs an empty state (with one clear call to action) and skeleton loading.
- Agent running state: progress steps plus a Stop button.
- Errors in plain words: "Model not reachable at localhost:11434 — Check settings".
- Offline: "Changes saved locally".

**Responsive:**
- ≥1440px: all three panels.
- 1280px: the context panel collapses to an icon rail.
- 1024px: the intelligence panel becomes an overlay drawer.
- Mobile: review mode only (read the page, approve or dismiss suggestions, view visibility).

**Accessibility:**
- WCAG 2.2 AA contrast.
- Focus ring: 2px primary with a 2px offset.
- All highlights are distinguishable without colour.
- Full keyboard paths; ARIA live region for the agent's progress.

**Shortcuts:** ⌘K command palette, ⌘↵ run agent, J/K next/previous suggestion, A accept, D dismiss, ⌘\ toggle panels.

## A11. Microcopy glossary
- **Entity coverage** → "Does this page clearly name the people, products, places and ideas it talks about?"
- **Answer readiness** → "Could an AI give a correct answer using only this page?"
- **Passage** → "A section that should make sense even if quoted on its own."
- **Originality** → "What this page says that the top results don't."
- **Blocker** → "Fix before publishing — this could cause a wrong or missing AI answer."
- Tone: calm, specific, no hype. Use "Consider" for Low impact and "Fix" for blockers.

---

# PART B — GOOGLE STITCH PROMPT PACK

**Stitch setup**
- Platform: **Web**.
- Use the highest-quality generation mode available for Prompts 1–2. Faster mode is fine for the rest.
- After Prompt 1, lock fonts and colours in Stitch's theme controls if they drift.
- Generate **one screen per prompt**. Then refine with one or two changes per prompt (Part C).

**Sample business used in all screens (fictional):** *Fernhill Bookkeeping* — bookkeeping and fractional CFO services for creative agencies, Austin, TX. Target query: "bookkeeping for creative agencies".

---

### PROMPT 1 — Content Optimizer (hero screen; sets the design system)

```
Design the main Content Optimizer screen of "Aentio", a self-hosted, open-source content optimization web app that helps pages get understood, quoted and cited by AI search engines (AEO/GEO) using the business's own knowledge graph. Desktop 1440px.

DESIGN SYSTEM (use on every future screen):
- Calm, minimal B2B SaaS in the spirit of Linear and Notion. Not a cluttered SEO dashboard.
- Fonts: Inter for UI (14px body, tabular numbers), Source Serif 4 18px for editor content, JetBrains Mono for code.
- Colors: background #FAFAF9, surfaces #FFFFFF, borders #E7E5E4 (1px), text #1C1917, muted #78716C, primary indigo #4338CA (soft #EEF2FF). Status only: green #15803D, amber #B45309, red #B91C1C, blue #1D4ED8.
- 8px spacing, 12px card radius, 8px button radius, pill chips, shadows only on popovers. Lucide-style 16px icons, used sparingly.

LAYOUT (three zones under a slim top bar):
- Top bar: breadcrumb "Library / Agency bookkeeping", "Draft" pill, small badge "Local model · Ollama", buttons "Run agent" (primary) and "Publish".
- Left context panel (280px, collapsible): Target query "bookkeeping for creative agencies"; intent chip "Commercial"; page type "Service page"; audience "Agency owners"; region "Austin, TX"; business entity chips (Fernhill Bookkeeping · Organization, Agency bookkeeping · Service, Fractional CFO · Service, Austin TX · Place); "Approved facts" list with check icons and verified dates (e.g. "Plans from $349/mo · verified Sep 2026"); "Competitors: 7 included · 3 excluded".
- Center editor (max 720px): realistic draft with H1 "Bookkeeping for Creative Agencies: What It Costs and What You Get". Show highlights that never rely on color alone: amber dashed underline for a missing entity, blue dotted underline for a claim needing a source, red dotted underline on the price "$299/mo", which conflicts with an approved fact, a green left bar on one strong answer paragraph, red wavy underline on vague filler. Small gutter glyphs next to highlighted lines. A floating selection toolbar over one sentence: "Make answer-first · Name the entity · Add source · Add FAQ · Simplify". Editor toolbar with layer toggles: Entities, Claims, Answers, Issues. Bottom bar: 1,284 words · 6 min read · Grade 8 · Outline · "Saved locally".
- Right Intelligence panel (380px) with a slim vertical icon tab rail: Overview, Entities, Answers, Evidence, Passages, Structure. Overview is active and shows:
  - Label "Almost ready" with "3 blockers" and a small muted "72" and tooltip "Directional, not a ranking prediction".
  - Five labeled horizontal bars with bands: Entities (Fair), Answers (Weak), Evidence (Weak), Passages (Fair), Originality (Strong).
  - Three recommendation cards, each with title, one-line reason, impact pill, 3-dot confidence, and buttons Apply / Edit / Explain / Dismiss:
    1. "Answer the question in the first two sentences" — High — "Your intro starts with company history; AI answers usually quote the opening passage."
    2. "Price conflicts with your Entity Hub" — High — "Draft says from $299/mo; verified fact is from $349/mo."
    3. "Name Fernhill in the 'How it works' section" — Medium — "This section says 'we' 9 times; a quoted passage would lose attribution."

Realistic content everywhere, no lorem ipsum, no stock photos. Professional, quiet, trustworthy.
```

---

### PROMPT 2 — Optimizer: Agent review state

```
Using the same Aentio design system and three-zone Content Optimizer layout, design the "Agent review" state.

- The right panel becomes "Agent run" with a header "Improve answers & evidence", a Stop button, and a plan checklist with check icons: "Read draft", "Compared with 7 competitor pages", "Checked 14 claims against Entity Hub", "Proposed 6 edits". Footer in muted small text: "Local model · 18.2k tokens · 41s".
- The center editor shows suggestions as tracked changes: inserted text underlined in indigo with soft indigo background, deleted text struck through in muted red. Each change has small inline ✓ and ✕ buttons. One rewritten opening paragraph now answers directly: "Fernhill Bookkeeping provides monthly bookkeeping and fractional CFO support for creative agencies in Austin, with plans from $349 per month."
- A sticky review bar at the bottom of the editor: "6 suggestions · 2 of 6" with Previous/Next, keyboard hints "J / K · A accept · D dismiss", and buttons "Accept all in Answers" and "Discard all".
- A small note above the editor: "Nothing is saved until you accept."

Keep it calm and focused. Changes must be clearly readable without relying on color alone.
```

---

### PROMPT 3 — Home dashboard

```
Using the Aentio design system, design the Home screen.

- Left sidebar (240px): logo "Aentio", workspace switcher "Fernhill Bookkeeping", nav: Home (active), Optimize, Briefs, Library, Entity Hub, AI Visibility, then Settings at the bottom with a small green status dot "Self-hosted · healthy".
- Top: greeting "Good afternoon, Sami" and one sentence: "4 pages need attention · 1 fact change affects 7 pages". Buttons: "Optimize a page" (primary), "Import URL", "Create brief". A ⌘K search field.
- Main element: an "Attention queue" list. Each row shows page title, URL, reason pill (Fact conflict, Lost AI mention, Weak direct answer, Missing entity, Stale 180d+), impact pill, and an "Open" button. Use 5 realistic rows about bookkeeping, fractional CFO, agency cash flow, Xero vs QuickBooks for agencies, and pricing.
- A row of four compact metric tiles, each with value, 30-day sparkline, and a one-line plain definition: Pages ready 18/42; Entity consistency 86%; AI mention rate 31%; Fresh pages 74%.
- A "Recent fact changes" card: "Starter plan price $299 → $349 · used on 7 pages · Review pages".
- A small activity feed: suggestions accepted, schema generated, prompt run completed.

Compact, calm, clear hierarchy. Do not make it look like a generic admin dashboard.
```

---

### PROMPT 4 — New Optimization: Research step

```
Using the Aentio design system, design step 3 of a 4-step "New optimization" wizard. Show a horizontal stepper at the top: Topic & intent ✓ · Business context ✓ · Research (active) · Brief. Each step is clickable and the user can skip.

- Left (wider) card "Search competitors" for "bookkeeping for creative agencies": a compact table with include toggles and columns Rank, Page (fictional domains), Format (Vendor page, Blog, Directory, Forum), Words, Entity overlap (small bar). 7 rows included; 3 rows greyed out and auto-excluded, each with a reason ("Forum thread — different format", "Directory listing", "Word count outlier").
- Right card "AI answer landscape": a short summary of what current AI answers say, the sources they cite (3 small source rows), and attribute chips showing what answers include: Definition ✓, Pricing ✓, Comparison ✓, Process ✗, Proof ✗. A callout: "No AI answer mentions agency-specific job costing — an originality opportunity."
- Below: "Questions people ask" list with source tags (Google, AI answers, Reddit) and an "Add to brief" checkbox on each.
- Footer bar: "Back" and "Build brief" (primary).

Clean, scannable, progressive disclosure.
```

---

### PROMPT 5 — Brief Builder

```
Using the Aentio design system, design the Brief Builder screen.

- Left panel "Source pool" with tabs: Competitor headings · Questions · Entity Hub facts · AI answer attributes. Items are draggable rows with a drag handle and a small source tag.
- Center: an editable outline of section cards for the page "Bookkeeping for Creative Agencies". Each card shows the H2 heading, a purpose pill (Answer, Explain, Compare, Prove), target entity chips, required facts with check icons, a one-line "answer-first" stub in muted italic, and a word range like "120–200 words". Show 5 cards, one being dragged with a drop indicator.
- Right panel: brief settings (tone, reading level, audience), "Notes for writer" text area, and export buttons: Markdown, PDF, "Share read-only link", and primary "Send to editor".

Feels like a calm planning tool, not a form.
```

---

### PROMPT 6 — Entity Hub

```
Using the Aentio design system, design the Entity Hub, the business knowledge graph.

- Header: "Entity Hub" with a List / Graph toggle (List active), search, type filter pills (All, Organization, Service, Person, Place, Concept, Source), and buttons "Import" and "Add entity" (primary).
- Main list table: Name, Type chip, Used on (pages), Facts, Last verified, Health pill (Healthy, Needs review, Conflict). Rows: Fernhill Bookkeeping, Agency bookkeeping, Fractional CFO, Job costing, Austin TX, Dana Reyes (Founder), Xero, QuickBooks Online.
- A right detail drawer (420px) for "Agency bookkeeping": canonical name, aliases chips, type "Service", one-sentence definition, sameAs links (Wikidata, LinkedIn, Google Business Profile) with small link icons, an @id URI in monospace, a "Verified facts" table (Fact, Value, Source, Verified, Owner) including "Starter price · $349/mo · pricing page · Sep 2026", a relationships list (offered by Fernhill Bookkeeping, serves Creative agencies, located in Austin TX), a mini relationship graph, a usage line "Used on 12 pages · Missing from 3 priority pages · 1 conflict", and buttons "Verify facts" and "Generate schema".

Governance-first: precise, trustworthy, readable.
```

---

### PROMPT 7 — AI Visibility

```
Using the Aentio design system, design the AI Visibility screen.

- Header: "AI Visibility", prompt-set tabs (Pricing, Comparisons, How-to), engine filter pills (configured by the user), and buttons "Run now" and "Add prompts".
- Main table: Prompt, Engines (small labelled chips, no brand logos), Mention rate shown as "3/5 runs", Status pill (Cited, Mentioned, Absent), Our URL cited, Competitors cited, 30-day trend sparkline, Last run. 6 realistic prompts like "best bookkeeping service for creative agencies", "how much does agency bookkeeping cost", "fractional CFO vs bookkeeper".
- Right detail panel for the selected prompt (status Absent): an answer snapshot card with competitor names highlighted, a "Sources cited" list, a "Missing attributes" checklist (Definition ✓, Pricing ✗, Comparison ✓, Process ✗, Proof ✗, Limitations ✗), and buttons "Fix in optimizer" (primary) and "Create brief".
- An always-visible muted methodology footer: "5 sampled runs per engine · Oct 14, 2026 · AI answers vary — treat as directional."

Honest, analytical, calm. No hype.
```

---

### PROMPT 8 — Publish & Schema

```
Using the Aentio design system, design the Publish screen.

- Top: a pre-publish checklist banner "2 blockers · 3 warnings" with expandable items and buttons "Fix" and a quieter "Publish anyway (logged)".
- Left column: previews in tabs: Search result, Social card, and "AI answer preview" showing the passage most likely to be quoted, with its source attribution.
- Center: a schema section with toggles for Article, Service, Organization, FAQPage, BreadcrumbList. A note: "Built from your Entity Hub · shared @id across site". A JSON-LD code panel in JetBrains Mono with a green "Valid" status and a copy button.
- Right column: destination cards: WordPress (connected), Markdown, HTML, Git commit, JSON-LD, CSV entity report. Below them a "Self-hosted status" card: model "Ollama · local", storage "/data/aentio", tokens this month, last backup "2 hours ago".
- Primary button: "Publish to WordPress".
```

---

### PROMPT 9 — Library / Audit

```
Using the Aentio design system, design the Library screen.

- Header: "Library", saved views tabs (All pages, Clusters, Needs attention), filter pills (Readiness, Cluster, Owner, Updated), and buttons "Import" (menu: URL, Sitemap, WordPress, CSV) and "New page".
- Main table with checkbox selection: Title + URL, Cluster, Readiness pill (Ready, Almost ready, Needs work), Entity consistency %, AI mentions, Traffic trend sparkline, Last updated, Owner avatar. 10 realistic rows for a bookkeeping firm.
- When 3 rows are selected, show a bulk action bar: "Audit", "Re-check facts", "Export report".
- An empty-state variant note is not needed; keep the populated state.
```

---

### PROMPT 10 — First-run setup (self-host)

```
Using the Aentio design system, design step 2 of a 5-step first-run setup wizard, centered in a calm 720px card. Stepper: Workspace ✓ · AI model (active) · Search data · Import entities · Privacy.

- Title "Choose your AI model" and subtext "Aentio never sends your content anywhere you don't choose."
- Three selectable option cards: "Local (Ollama)" (selected, with a "Recommended for privacy" pill), "OpenAI-compatible endpoint", "Hosted provider (your API key)". Each has a one-line privacy note.
- Fields for the selected option: Endpoint "http://localhost:11434", model dropdown, and a "Test connection" button with a green success state "Connected · 41 tokens/s".
- Footer: Back, "Skip for now", and "Continue" (primary).
```

---

### PROMPT 11 — Dark mode + mobile review

```
Create a dark-mode version of the Content Optimizer screen using: background #0C0C0E, surfaces #16161A, borders #27272A, text #FAFAFA, muted #A1A1AA, primary #818CF8; status colors one step lighter. Keep layout identical.
```
```
Design a mobile (390px) "Review mode" screen for Aentio: page title at top, readiness label "Almost ready · 3 blockers", then a swipeable stack of recommendation cards with large Accept and Dismiss buttons, and a bottom tab bar: Review, Pages, Visibility.
```

---

# PART C — REFINEMENT MICRO-PROMPTS AND CHANGE NOTES

**Use one or two of these per generation:**
- "Make the right Intelligence panel 360px and tighten card padding to 12px."
- "Replace any large score circle with a text label 'Almost ready' and a small muted number."
- "Add gutter glyphs (◆ § ✓ !) beside highlighted lines so highlights don't rely on color."
- "Show the Entities tab active: chips grouped 'From your business' and 'From top results', each with status and a placement range like 'Body 2–4 · in an H2'."
- "Show the Evidence tab active: a claims ledger table with columns Claim, Linked fact/source, Status (Verified, Unsourced, Conflict) and an Originality meter 'Unique vs top 7: 34%'."
- "Show the Passages tab: list each H2 section with length, 'Answer-first' check, 'Names entity' check, and a band dot."
- "Switch the Entity Hub to Graph view: typed node cards connected by labelled edges, with the detail drawer still open."
- "Add a ⌘K command palette overlay with actions: Run agent, Add entity, Jump to page, Toggle highlights."
- "Show skeleton loading states for the Intelligence panel."
- "Reduce visual weight: fewer borders, more whitespace, same information."

**What changed from the earlier version:**
1. **Prompts split one screen at a time.** Stitch's official guidance says to focus on one screen and make one or two changes per prompt. The earlier version packed five screens into one prompt.
2. **Exact design tokens** (hex values, fonts, sizes) replace "indigo or teal", so the screens stay consistent.
3. **No vanity score.** The earlier version said "don't chase a score" and then led with a 78/100 circle. Now the label leads and the number is secondary.
4. **Accessible highlights**: underline styles plus gutter glyphs, not colour fills alone.
5. **Agent edits as tracked changes**, with a dedicated review state. Earlier, "user approves" had no UI.
6. **Missing best practices added:** competitor include/exclude (Surfer/NeuronWriter), placement-split ranges (NeuronWriter), Brief Builder (Frase), existing-URL audit.
7. **GEO-specific features:** passage map, claims ledger with Entity Hub conflict detection, originality check, fact-change propagation.
8. **Honest AI Visibility**: sampled runs, variance, and a methodology footer, without implying data from engines that have no API.
9. **Self-host made real:** a first-run model and data setup, privacy defaults, token usage.
10. **States, responsive breakpoints, shortcuts, and dark/mobile prompts** are all specified.
11. **Entity Hub list-first**: list view for governance, graph as a toggle, plus `sameAs`, `@id`, and verified-date fields that drive schema.
12. **A fictional sample brand**, used consistently across all screens.
