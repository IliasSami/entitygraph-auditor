/**
 * Deterministic sample fixture: "Northwind Roofing" — a local-service page.
 *
 * This is the single source of truth for mock mode. It is intentionally rich
 * enough to exercise every report surface (entities, EAV, triples, fan-out,
 * passages, claims, recommendations, technical flags). It is NOT a real audit
 * and the UI labels it as sample data wherever it is shown.
 *
 * Offsets are derived from the built document so that "jump to passage" links
 * are always internally consistent.
 */

import type {
  AuditReport,
  Claim,
  ComponentScore,
  EAVRow,
  Entity,
  EvidenceSource,
  FanoutQuery,
  CoverageRow,
  Finding,
  Heading,
  Passage,
  PassageSkill,
  ScoreKey,
  Section,
  SemanticTriple,
  TechnicalFlag,
} from "@/lib/types";

interface PassageSeed {
  id: string;
  section_id: string;
  text: string;
  named_subject: boolean;
  answer_first: boolean;
  answer_shape: Passage["answer_shape"];
  issues: string[];
  strengths: string[];
}

interface SectionSeed {
  id: string;
  heading?: { level: number; text: string; id: string };
  passages: PassageSeed[];
}

const SECTION_SEEDS: SectionSeed[] = [
  {
    id: "sec-hero",
    heading: { level: 1, id: "h-roof-replacement", text: "Roof Replacement & Roof Repair in Bellingham, WA" },
    passages: [
      {
        id: "p-hero-1",
        section_id: "sec-hero",
        text: "Northwind Roofing is a family-owned roofing contractor serving Bellingham and Whatcom County, Washington. We install and repair asphalt-shingle roofs for homeowners, and every project starts with a free roof inspection.",
        named_subject: true,
        answer_first: true,
        answer_shape: "definition",
        issues: [],
        strengths: [
          "Names the central entity in the first sentence",
          "States the service and the service area up front",
        ],
      },
      {
        id: "p-hero-2",
        section_id: "sec-hero",
        text: "We have completed more than 1,200 roof replacements across Whatcom County and have been serving the area for many years.",
        named_subject: true,
        answer_first: false,
        answer_shape: "proof_block",
        issues: [
          "Vague time reference: \u201cmany years\u201d is not verifiable",
          "Volume claim has no dated first-party record attached",
        ],
        strengths: ["States a concrete first-party project volume"],
      },
    ],
  },
  {
    id: "sec-materials",
    heading: { level: 2, id: "h-what-we-install", text: "What we install" },
    passages: [
      {
        id: "p-mat-1",
        section_id: "sec-materials",
        text: "Asphalt shingles are installed to the manufacturer's published specifications, including the required underlayment and ventilation for Western Washington's wet climate.",
        named_subject: false,
        answer_first: false,
        answer_shape: "procedure",
        issues: [
          "The sentence subject is the material, not the contractor",
          "Passive construction hides who performs the work",
        ],
        strengths: ["Process detail (underlayment, ventilation) is specific"],
      },
      {
        id: "p-mat-2",
        section_id: "sec-materials",
        text: "Reflective shingles can reduce summer cooling costs by up to 40%, which makes them a strong choice for south-facing roofs.",
        named_subject: false,
        answer_first: false,
        answer_shape: "proof_block",
        issues: [
          "Unsupported numeric claim: \u201cup to 40%\u201d has no dated source",
          "Causal claim is stated as a general fact rather than a qualified estimate",
        ],
        strengths: ["Connects material choice to a homeowner benefit"],
      },
    ],
  },
  {
    id: "sec-trust",
    heading: { level: 2, id: "h-trust", text: "Licensing, insurance and warranty" },
    passages: [
      {
        id: "p-trust-1",
        section_id: "sec-trust",
        text: "Northwind Roofing is registered with the Washington State Department of Labor & Industries. We carry general liability coverage and provide a two-year workmanship warranty on every installation.",
        named_subject: true,
        answer_first: true,
        answer_shape: "proof_block",
        issues: ["Registration number is not stated, so it cannot be cross-checked"],
        strengths: ["Trust entities and the warranty term are stated explicitly"],
      },
    ],
  },
  {
    id: "sec-cta",
    heading: { level: 2, id: "h-schedule", text: "Schedule your free roof inspection" },
    passages: [
      {
        id: "p-cta-1",
        section_id: "sec-cta",
        text: "Call us or send the form below to schedule a free inspection. We will confirm your appointment within one business day.",
        named_subject: false,
        answer_first: true,
        answer_shape: "cta",
        issues: [
          "No phone number, hours or booking entity is present",
          "Response-time promise has no service-level context",
        ],
        strengths: ["Clear, single next step for the reader"],
      },
    ],
  },
  {
    id: "sec-area",
    heading: { level: 2, id: "h-service-area", text: "Service area" },
    passages: [
      {
        id: "p-area-1",
        section_id: "sec-area",
        text: "We serve Bellingham, Fairhaven, Lynden, Ferndale and the surrounding areas. Contact us to confirm coverage for your address.",
        named_subject: false,
        answer_first: false,
        answer_shape: "shortlist",
        issues: [
          "Named sibling-page localities (Lynden, Ferndale) are not linked",
          "Whatcom County is not restated in the section",
        ],
        strengths: ["Names multiple localities rather than a generic region"],
      },
    ],
  },
];

interface BuiltDocument {
  document: string;
  headings: Heading[];
  passages: Passage[];
  sections: Section[];
}

function buildDocument(): BuiltDocument {
  const parts: string[] = [];
  const headings: Heading[] = [];
  const passages: Passage[] = [];
  const sections: Section[] = [];
  let cursor = 0;

  const push = (chunk: string): number => {
    const start = cursor;
    parts.push(chunk);
    cursor += chunk.length;
    return start;
  };

  for (const seed of SECTION_SEEDS) {
    let heading: Heading | null = null;
    if (seed.heading) {
      const offset = push(`${"#".repeat(seed.heading.level)} ${seed.heading.text}\n\n`);
      heading = { level: seed.heading.level, text: seed.heading.text, id: seed.heading.id, offset };
      headings.push(heading);
    }
    const sectionPassages: Passage[] = [];
    for (const seedPassage of seed.passages) {
      const start = push(seedPassage.text);
      const passage: Passage = {
        passage_id: seedPassage.id,
        section_id: seed.id,
        text: seedPassage.text,
        word_count: seedPassage.text.trim().split(/\s+/).length,
        start_offset: start,
        end_offset: start + seedPassage.text.length,
        named_subject: seedPassage.named_subject,
        answer_first: seedPassage.answer_first,
        answer_shape: seedPassage.answer_shape,
        issues: seedPassage.issues,
      };
      passages.push(passage);
      sectionPassages.push(passage);
      push("\n\n");
    }
    sections.push({
      section_id: seed.id,
      heading,
      passages: sectionPassages,
      raw_text: sectionPassages.map((p) => p.text).join("\n\n"),
      word_count: sectionPassages.reduce((sum, p) => sum + p.word_count, 0),
    });
  }

  return { document: parts.join(""), headings, passages, sections };
}

const BUILT = buildDocument();
export const NORTHWIND_DOCUMENT = BUILT.document;
export const NORTHWIND_PASSAGES = BUILT.passages;
export const NORTHWIND_HEADINGS = BUILT.headings;
export const NORTHWIND_SECTIONS = BUILT.sections;

const PASSAGE_SEED_META = new Map(
  SECTION_SEEDS.flatMap((s) => s.passages).map((p) => [p.id, p] as const),
);

export const NORTHWIND_PASSAGE_SKILLS: PassageSkill[] = NORTHWIND_PASSAGES.map((p) => ({
  passage_id: p.passage_id,
  strengths: PASSAGE_SEED_META.get(p.passage_id)?.strengths ?? [],
  issues: p.issues,
}));

const passageById = (id: string): Passage => {
  const found = NORTHWIND_PASSAGES.find((p) => p.passage_id === id);
  if (!found) throw new Error(`Unknown passage in fixture: ${id}`);
  return found;
};

/** Build an occurrence anchored to a real substring of a passage. */
function occurrence(passageId: string, fragment: string) {
  const passage = passageById(passageId);
  const index = passage.text.indexOf(fragment);
  const start = index >= 0 ? passage.start_offset + index : passage.start_offset;
  const end = index >= 0 ? start + fragment.length : passage.end_offset;
  return { passage_id: passageId, start_offset: start, end_offset: end, sentence: fragment };
}

const ENTITIES: Entity[] = [
  {
    entity_id: "ent-northwind",
    canonical_name: "Northwind Roofing",
    kind: "central",
    confidence: "high",
    salience: 0.96,
    occurrences: [
      occurrence("p-hero-1", "Northwind Roofing is a family-owned roofing contractor"),
      occurrence("p-trust-1", "Northwind Roofing"),
      occurrence("p-hero-1", "We install and repair asphalt-shingle roofs"),
    ],
    aliases: ["Northwind", "Northwind Roofing Co."],
    is_central: true,
    method: "deterministic",
    wikidata_id: null,
  },
  {
    entity_id: "ent-roof-replacement",
    canonical_name: "Roof replacement",
    kind: "product_service",
    confidence: "high",
    salience: 0.82,
    occurrences: [
      occurrence("p-hero-2", "roof replacements"),
      occurrence("p-hero-1", "install and repair asphalt-shingle roofs"),
    ],
    aliases: ["Roof replacement", "Roof repair"],
    is_central: false,
    method: "dictionary",
    wikidata_id: null,
  },
  {
    entity_id: "ent-bellingham",
    canonical_name: "Bellingham, Washington",
    kind: "location",
    confidence: "high",
    salience: 0.74,
    occurrences: [occurrence("p-hero-1", "Bellingham and Whatcom County, Washington")],
    aliases: ["Bellingham", "Bellingham, WA"],
    is_central: false,
    method: "ner_local",
    wikidata_id: "Q430267",
  },
  {
    entity_id: "ent-whatcom",
    canonical_name: "Whatcom County",
    kind: "location",
    confidence: "medium",
    salience: 0.55,
    occurrences: [
      occurrence("p-hero-2", "Whatcom County"),
      occurrence("p-hero-1", "Whatcom County"),
    ],
    aliases: ["Whatcom"],
    is_central: false,
    method: "ner_local",
    wikidata_id: "Q156652",
  },
  {
    entity_id: "ent-asphalt",
    canonical_name: "Asphalt shingles",
    kind: "material",
    confidence: "high",
    salience: 0.6,
    occurrences: [
      occurrence("p-mat-1", "Asphalt shingles"),
      occurrence("p-hero-1", "asphalt-shingle roofs"),
    ],
    aliases: ["Asphalt shingle", "Composition shingles"],
    is_central: false,
    method: "dictionary",
    wikidata_id: null,
  },
  {
    entity_id: "ent-inspection",
    canonical_name: "Roof inspection",
    kind: "process",
    confidence: "medium",
    salience: 0.58,
    occurrences: [
      occurrence("p-hero-1", "free roof inspection"),
      occurrence("p-cta-1", "schedule a free inspection"),
    ],
    aliases: ["Roof inspection", "Free inspection"],
    is_central: false,
    method: "dictionary",
    wikidata_id: null,
  },
  {
    entity_id: "ent-wa-li",
    canonical_name: "Washington State Department of Labor & Industries registration",
    kind: "standard",
    confidence: "low",
    salience: 0.4,
    occurrences: [occurrence("p-trust-1", "Washington State Department of Labor & Industries")],
    aliases: ["WA L&I", "Labor & Industries"],
    is_central: false,
    method: "ner_local",
    wikidata_id: null,
  },
  {
    entity_id: "ent-warranty",
    canonical_name: "Two-year workmanship warranty",
    kind: "proof",
    confidence: "high",
    salience: 0.5,
    occurrences: [
      occurrence("p-hero-1", "two-year workmanship warranty"),
      occurrence("p-trust-1", "two-year workmanship warranty"),
    ],
    aliases: ["Workmanship warranty"],
    is_central: false,
    method: "deterministic",
    wikidata_id: null,
  },
];

const EAV_ROWS: EAVRow[] = [
  {
    eav_id: "eav-service",
    entity_name: "Northwind Roofing",
    attribute: "primary_service",
    value: "Roof replacement and roof repair",
    status: "explicit",
    evidence_excerpt: "We install and repair asphalt-shingle roofs for homeowners",
    passage_id: "p-hero-1",
    confidence: "high",
    notes: null,
    is_required_by_page_type: true,
  },
  {
    eav_id: "eav-area",
    entity_name: "Northwind Roofing",
    attribute: "service_area",
    value: "Bellingham and Whatcom County, Washington",
    status: "explicit",
    evidence_excerpt: "serving Bellingham and Whatcom County, Washington",
    passage_id: "p-hero-1",
    confidence: "high",
    notes: null,
    is_required_by_page_type: true,
  },
  {
    eav_id: "eav-phone",
    entity_name: "Northwind Roofing",
    attribute: "contact_phone",
    value: null,
    status: "missing",
    evidence_excerpt: null,
    passage_id: "p-cta-1",
    confidence: "high",
    notes: "A local-service page must expose a callable contact method above the form.",
    is_required_by_page_type: true,
  },
  {
    eav_id: "eav-years",
    entity_name: "Northwind Roofing",
    attribute: "years_in_business",
    value: "many years",
    status: "vague",
    evidence_excerpt: "have been serving the area for many years",
    passage_id: "p-hero-2",
    confidence: "medium",
    notes: "A founding year or \u201csince 2008\u201d is verifiable; \u201cmany years\u201d is not.",
    is_required_by_page_type: true,
  },
  {
    eav_id: "eav-licence",
    entity_name: "Northwind Roofing",
    attribute: "licence_registration",
    value: "Registered with the Washington State Department of Labor & Industries",
    status: "unverified",
    evidence_excerpt: "registered with the Washington State Department of Labor & Industries",
    passage_id: "p-trust-1",
    confidence: "medium",
    notes: "Registration number is not stated, so the claim cannot be cross-checked.",
    is_required_by_page_type: true,
  },
  {
    eav_id: "eav-financing",
    entity_name: "Northwind Roofing",
    attribute: "financing_options",
    value: null,
    status: "not_applicable",
    evidence_excerpt: null,
    passage_id: null,
    confidence: "high",
    notes: "Financing is handled on the sibling \u201croof financing\u201d page and is not required here.",
    is_required_by_page_type: false,
  },
];

const TRIPLES: SemanticTriple[] = [
  {
    triple_id: "tri-1",
    subject: "Northwind Roofing",
    predicate: "is a",
    object_: "roofing contractor",
    triple_type: "category",
    status: "explicit",
    evidence_excerpt: "Northwind Roofing is a family-owned roofing contractor",
    passage_id: "p-hero-1",
    confidence: "high",
    notes: null,
  },
  {
    triple_id: "tri-2",
    subject: "Northwind Roofing",
    predicate: "provides",
    object_: "roof replacement and repair",
    triple_type: "capability",
    status: "explicit",
    evidence_excerpt: "We install and repair asphalt-shingle roofs",
    passage_id: "p-hero-1",
    confidence: "high",
    notes: null,
  },
  {
    triple_id: "tri-3",
    subject: "Northwind Roofing",
    predicate: "serves",
    object_: "Bellingham, Washington",
    triple_type: "geography",
    status: "explicit",
    evidence_excerpt: "serving Bellingham and Whatcom County, Washington",
    passage_id: "p-hero-1",
    confidence: "high",
    notes: null,
  },
  {
    triple_id: "tri-4",
    subject: "Northwind Roofing",
    predicate: "installs",
    object_: "asphalt shingles",
    triple_type: "capability",
    status: "explicit",
    evidence_excerpt: "Asphalt shingles are installed to the manufacturer's published specifications",
    passage_id: "p-mat-1",
    confidence: "medium",
    notes: "Stated in the passive voice, so the subject is implied rather than named.",
  },
  {
    triple_id: "tri-5",
    subject: "Asphalt shingles",
    predicate: "reduce",
    object_: "summer cooling costs by up to 40%",
    triple_type: "cause_effect",
    status: "unsupported",
    evidence_excerpt: "can reduce summer cooling costs by up to 40%",
    passage_id: "p-mat-2",
    confidence: "low",
    notes: "Effect size is unsourced and should be qualified or evidenced.",
  },
  {
    triple_id: "tri-6",
    subject: "Two-year workmanship warranty",
    predicate: "covers",
    object_: "installation labour",
    triple_type: "capability",
    status: "implied",
    evidence_excerpt: "provide a two-year workmanship warranty on every installation",
    passage_id: "p-trust-1",
    confidence: "medium",
    notes: "What the warranty does and does not cover is not enumerated.",
  },
  {
    triple_id: "tri-7",
    subject: "Northwind Roofing",
    predicate: "charges",
    object_: "typical residential roof replacement price",
    triple_type: "price",
    status: "missing",
    evidence_excerpt: null,
    passage_id: null,
    confidence: "high",
    notes: "No price signal or cost range appears anywhere on the page.",
  },
];

interface FanoutSeed {
  q: string;
  importance: 1 | 2 | 3;
  source: FanoutQuery["source"];
  shape: FanoutQuery["answer_shape"];
  scope: FanoutQuery["scope"];
  intent: FanoutQuery["intent"];
  coverage: CoverageRow["status"];
  coverage_score: number;
  matched: string[];
  gap_reason?: string;
  destination_page?: string;
}

/** 18 fan-out queries, all simulated (no search-console connection). */
const FANOUT_SEEDS: FanoutSeed[] = [
  { q: "roof replacement cost bellingham wa", importance: 3, source: "generated_hypothesis", shape: "pricing_fact", scope: "this_page", intent: "commercial", coverage: "missing", coverage_score: 0, matched: [], gap_reason: "No price range, financing or cost drivers are stated on the page." },
  { q: "roof replacement bellingham", importance: 3, source: "generated_hypothesis", shape: "shortlist", scope: "this_page", intent: "local", coverage: "covered", coverage_score: 1, matched: ["p-hero-1"] },
  { q: "best roofing contractor in bellingham", importance: 3, source: "generated_hypothesis", shape: "shortlist", scope: "this_page", intent: "commercial", coverage: "partial", coverage_score: 0.5, matched: ["p-hero-1"], gap_reason: "Selection criteria and proof are thin; the page does not say why it is the best choice." },
  { q: "how much does a new roof cost in whatcom county", importance: 3, source: "generated_hypothesis", shape: "pricing_fact", scope: "this_page", intent: "commercial", coverage: "missing", coverage_score: 0, matched: [], gap_reason: "Cost is never quantified; \u201cwritten estimates\u201d are promised without a range." },
  { q: "signs you need a new roof", importance: 2, source: "generated_hypothesis", shape: "checklist", scope: "this_page", intent: "informational", coverage: "missing", coverage_score: 0, matched: [], gap_reason: "No diagnostic checklist or decision support is present." },
  { q: "how long does a roof replacement take", importance: 2, source: "generated_hypothesis", shape: "procedure", scope: "this_page", intent: "informational", coverage: "missing", coverage_score: 0, matched: [], gap_reason: "Timeline and process duration are not addressed." },
  { q: "asphalt shingle roof lifespan washington", importance: 2, source: "generated_hypothesis", shape: "definition", scope: "this_page", intent: "informational", coverage: "partial", coverage_score: 0.5, matched: ["p-mat-1"], gap_reason: "Installation is described, but expected service life is not." },
  { q: "are reflective shingles worth it in seattle", importance: 2, source: "generated_hypothesis", shape: "evaluation" as unknown as FanoutQuery["answer_shape"], scope: "this_page", intent: "evaluation", coverage: "partial", coverage_score: 0.5, matched: ["p-mat-2"], gap_reason: "Benefit is claimed with an unsourced 40% figure and no local climate context." },
  { q: "does homeowners insurance cover roof replacement", importance: 2, source: "generated_hypothesis", shape: "risk_explanation", scope: "sibling_page", intent: "informational", coverage: "excluded", coverage_score: 0, matched: [], gap_reason: "Belongs on the insurance-claims sibling page, not the core service page.", destination_page: "/services/insurance-claims" },
  { q: "roof inspection cost bellingham", importance: 2, source: "generated_hypothesis", shape: "pricing_fact", scope: "this_page", intent: "commercial", coverage: "covered", coverage_score: 1, matched: ["p-hero-1", "p-cta-1"] },
  { q: "licensed roofers bellingham", importance: 2, source: "generated_hypothesis", shape: "proof_block", scope: "this_page", intent: "commercial", coverage: "partial", coverage_score: 0.5, matched: ["p-trust-1"], gap_reason: "Registration is claimed without a number, so it cannot be verified." },
  { q: "whatcom county roofing company", importance: 2, source: "generated_hypothesis", shape: "shortlist", scope: "this_page", intent: "local", coverage: "covered", coverage_score: 1, matched: ["p-hero-1", "p-hero-2"] },
  { q: "metal vs asphalt shingles washington", importance: 1, source: "generated_hypothesis", shape: "comparison_verdict", scope: "this_page", intent: "comparison", coverage: "missing", coverage_score: 0, matched: [], gap_reason: "Only asphalt is discussed; no material comparison is offered." },
  { q: "roof replacement warranty coverage", importance: 2, source: "generated_hypothesis", shape: "proof_block", scope: "this_page", intent: "informational", coverage: "partial", coverage_score: 0.5, matched: ["p-trust-1"], gap_reason: "The two-year term is stated but exclusions and process are not." },
  { q: "emergency roof repair bellingham", importance: 1, source: "generated_hypothesis", shape: "cta", scope: "sibling_page", intent: "transactional", coverage: "excluded", coverage_score: 0, matched: [], gap_reason: "Emergency service is a separate offering and should not be folded into this page.", destination_page: "/services/emergency-repair" },
  { q: "how to choose a roofing contractor", importance: 2, source: "generated_hypothesis", shape: "checklist", scope: "this_page", intent: "research", coverage: "missing", coverage_score: 0, matched: [], gap_reason: "No selection guidance or vetting checklist is provided." },
  { q: "roof replacement lynden wa", importance: 1, source: "generated_hypothesis", shape: "shortlist", scope: "this_page", intent: "local", coverage: "partial", coverage_score: 0.5, matched: ["p-area-1"], gap_reason: "Lynden is named in the service area but has no dedicated sibling page or link." },
  { q: "ice dam prevention western washington", importance: 1, source: "generated_hypothesis", shape: "procedure", scope: "out_of_scope", intent: "informational", coverage: "excluded", coverage_score: 0, matched: [], gap_reason: "Topical but not part of this page's intent; keep it out of the denominator.", destination_page: "/blog/ice-dams" },
];

const FANOUT: FanoutQuery[] = FANOUT_SEEDS.map((seed, index) => ({
  query_id: `q-${String(index + 1).padStart(2, "0")}`,
  query_text: seed.q,
  origin: "simulated",
  source: seed.source,
  intent: seed.intent,
  importance: seed.importance,
  answer_shape: (["definition", "checklist", "procedure", "shortlist", "table", "comparison_verdict", "pricing_fact", "risk_explanation", "proof_block", "cta"].includes(seed.shape) ? seed.shape : "definition") as FanoutQuery["answer_shape"],
  scope: seed.scope,
}));

const COVERAGE_ROWS: CoverageRow[] = FANOUT_SEEDS.map((seed, index) => ({
  query_id: `q-${String(index + 1).padStart(2, "0")}`,
  query_text: seed.q,
  status: seed.coverage,
  matched_passage_ids: seed.matched,
  coverage_score: seed.coverage_score,
  gap_reason: seed.gap_reason ?? null,
  destination_page: seed.destination_page ?? null,
}));

const PASSAGE_FINDINGS: Finding[] = [
  {
    finding_id: "fnd-phone",
    category: "eav_gap",
    severity: "high",
    title: "No callable phone number or opening hours on a local-service page",
    what: "The contact section asks visitors to \u201ccall us\u201d but never states a phone number, so the primary local conversion action is not actionable and the required contact_phone attribute is missing.",
    where: {
      section_id: "sec-cta",
      passage_id: "p-cta-1",
      start_offset: passageById("p-cta-1").start_offset,
      end_offset: passageById("p-cta-1").end_offset,
      excerpt: passageById("p-cta-1").text,
    },
    why: { intent_or_query: "call a roofer bellingham", layer: "reader", entity: "Northwind Roofing", attribute: "contact_phone", eav_status: "missing", rule_id: "eav.required_attribute.missing" },
    how: {
      suggested_rewrite: "Call Northwind Roofing on (360) 555-0142, Monday to Saturday, 7:00\u201318:00, or send the form below and we will confirm your free inspection within one business day.",
      verification_condition: "A tel: link that resolves to a monitored number appears in the contact block, and the opening hours match the Google Business Profile.",
      implementation_steps: ["Add the primary phone number to the page header and contact section", "Wrap it in a tel: link for mobile", "State opening hours next to the number"],
    },
    evidence: ["Required attribute contact_phone has status \u201cmissing\u201d", "CTAs reference calling without a number"],
    confidence: "high",
    impact: 5,
    confidence_numeric: 5,
    effort: 1,
    priority_score: 25,
    status: "open",
  },
  {
    finding_id: "fnd-years",
    category: "vague_value",
    severity: "high",
    title: "Experienced-based trust signal is unverifiable (\u201cmany years\u201d)",
    what: "The page claims the business has been \u201cserving the area for many years\u201d. A relative phrase cannot be verified by a reader, an extractor or an AI answer engine.",
    where: {
      section_id: "sec-hero",
      passage_id: "p-hero-2",
      start_offset: passageById("p-hero-2").start_offset,
      end_offset: passageById("p-hero-2").end_offset,
      excerpt: "have been serving the area for many years",
    },
    why: { layer: "retrieval", entity: "Northwind Roofing", attribute: "years_in_business", eav_status: "vague", rule_id: "eav.vague_value" },
    how: {
      suggested_rewrite: "Northwind Roofing has been roofing homes in Whatcom County since 2008, and has completed more than 1,200 roof replacements.",
      verification_condition: "The founding year matches the business registration record and the project count is stored in the first-party project log.",
      implementation_steps: ["Replace the relative phrase with a founding year", "Attribute the project count to the internal project log"],
    },
    evidence: ["EAV attribute years_in_business is \u201cvague\u201d", "No dated first-party record supports the phrase"],
    confidence: "high",
    impact: 4,
    confidence_numeric: 5,
    effort: 1,
    priority_score: 20,
    status: "open",
  },
  {
    finding_id: "fnd-claim-40",
    category: "unsupported_claim",
    severity: "high",
    title: "Unsourced numeric claim: reflective shingles \u201creduce cooling costs by up to 40%\u201d",
    what: "A specific effect size is asserted without a dated study or manufacturer source, and the causal relationship is stated as a general fact.",
    where: {
      section_id: "sec-materials",
      passage_id: "p-mat-2",
      start_offset: passageById("p-mat-2").start_offset,
      end_offset: passageById("p-mat-2").end_offset,
      excerpt: "can reduce summer cooling costs by up to 40%",
    },
    why: { layer: "retrieval", entity: "Asphalt shingles", attribute: "cooling_cost_reduction", eav_status: "unverified", rule_id: "claim.numeric.unsupported" },
    how: {
      suggested_rewrite: "Manufacturer testing reports that reflective asphalt shingles can lower attic temperatures; measured cooling-cost savings vary widely by home and climate. We will confirm expected savings for your roof during the inspection.",
      verification_condition: "Either a dated, citable source accompanies the figure, or the number is removed and replaced with a qualified statement.",
      implementation_steps: ["Remove the 40% figure or attach a dated source with a link", "Qualify the claim as climate- and home-dependent"],
    },
    evidence: ["Claim ledger marks the statement as unverified", "No evidence source is attached to the triple"],
    confidence: "high",
    impact: 5,
    confidence_numeric: 5,
    effort: 3,
    priority_score: 8.3,
    status: "open",
  },
  {
    finding_id: "fnd-answer-first",
    category: "passage_structure",
    severity: "medium",
    title: "\u201cWhat we install\u201d passage is not answer-first and hides the actor",
    what: "The passage opens with the material in a passive construction, so a standalone extract does not name the contractor or answer the section question directly.",
    where: {
      section_id: "sec-materials",
      passage_id: "p-mat-1",
      start_offset: passageById("p-mat-1").start_offset,
      end_offset: passageById("p-mat-1").end_offset,
      excerpt: passageById("p-mat-1").text,
    },
    why: { layer: "retrieval", entity: "Asphalt shingles", rule_id: "passage.answer_first.missing" },
    how: {
      suggested_rewrite: "We install asphalt shingles to the manufacturer's published specifications, including the underlayment and ventilation Western Washington's wet climate requires.",
      verification_condition: "The passage names Northwind Roofing as the actor and the first sentence answers the section heading on its own.",
      implementation_steps: ["Rewrite the sentence in the active voice with the subject first", "Keep the specification detail"],
    },
    evidence: ["Passage has named_subject=false and answer_first=false"],
    confidence: "high",
    impact: 3,
    confidence_numeric: 4,
    effort: 1,
    priority_score: 12,
    status: "open",
  },
  {
    finding_id: "fnd-price",
    category: "commercial_completeness",
    severity: "medium",
    title: "No cost signal for a commercial local-service query set",
    what: "Four of the highest-importance simulated queries ask about cost, and the page contains no price range, cost driver or financing information.",
    where: {
      section_id: "sec-hero",
      passage_id: "p-hero-1",
      start_offset: passageById("p-hero-1").start_offset,
      end_offset: passageById("p-hero-1").end_offset,
      excerpt: "\u2026every project starts with a free roof inspection.",
    },
    why: { intent_or_query: "roof replacement cost bellingham wa", layer: "business", rule_id: "coverage.core_query.missing" },
    how: {
      suggested_rewrite: "Most residential roof replacements in Bellingham fall between $9,500 and $18,000, depending on roof size, pitch and material. Your written estimate itemises materials and labour before work begins.",
      verification_condition: "A dated cost range from at least 20 completed jobs is published, with its effective date shown.",
      implementation_steps: ["Publish a cost range with an effective date", "Add a small cost-driver table (size, pitch, material)", "Link to the financing sibling page"],
    },
    evidence: ["Coverage rows for cost queries are \u201cmissing\u201d", "No price entity or attribute appears on the page"],
    confidence: "medium",
    impact: 4,
    confidence_numeric: 4,
    effort: 2,
    priority_score: 8,
    status: "open",
  },
  {
    finding_id: "fnd-internal-links",
    category: "internal_linking",
    severity: "low",
    title: "Named sibling-page localities and services are not linked",
    what: "Lynden, Ferndale and the emergency-repair service are mentioned or implied but not linked to their dedicated pages, weakening topical architecture.",
    where: {
      section_id: "sec-area",
      passage_id: "p-area-1",
      start_offset: passageById("p-area-1").start_offset,
      end_offset: passageById("p-area-1").end_offset,
      excerpt: "We serve Bellingham, Fairhaven, Lynden, Ferndale and the surrounding areas.",
    },
    why: { layer: "retrieval", rule_id: "linking.sibling_page.unlinked" },
    how: {
      suggested_rewrite: "We serve Bellingham, Fairhaven, [Lynden](/service-areas/lynden), [Ferndale](/service-areas/ferndale) and the surrounding areas.",
      verification_condition: "Each mentioned locality links to an existing, indexable sibling page with matching content.",
      implementation_steps: ["Link named localities to their service-area pages", "Link the emergency-repair mention to its page"],
    },
    evidence: ["Destination pages identified in coverage rows", "No internal links exist in the parsed document"],
    confidence: "medium",
    impact: 2,
    confidence_numeric: 4,
    effort: 1,
    priority_score: 8,
    status: "open",
  },
];

const RECOMMENDATIONS: Finding[] = [
  PASSAGE_FINDINGS[0],
  PASSAGE_FINDINGS[1],
  PASSAGE_FINDINGS[2],
  PASSAGE_FINDINGS[4],
  PASSAGE_FINDINGS[3],
  PASSAGE_FINDINGS[5],
];

const CLAIMS: Claim[] = [
  {
    claim_id: "clm-1",
    statement: "We have completed more than 1,200 roof replacements across Whatcom County.",
    risk_tier: "ordinary",
    verification_state: "verified",
    passage_id: "p-hero-2",
    evidence_source_ids: ["src-project-log"],
    requires_substantiation: false,
    issue: null,
  },
  {
    claim_id: "clm-2",
    statement: "Reflective shingles can reduce summer cooling costs by up to 40%.",
    risk_tier: "ordinary",
    verification_state: "unverified",
    passage_id: "p-mat-2",
    evidence_source_ids: ["src-cooling-blog"],
    requires_substantiation: true,
    issue: "Numeric benefit is attributed to an undated third-party blog; no measured study is cited.",
  },
  {
    claim_id: "clm-3",
    statement: "Northwind Roofing is registered with the Washington State Department of Labor & Industries.",
    risk_tier: "high_stakes",
    verification_state: "verified",
    passage_id: "p-trust-1",
    evidence_source_ids: ["src-wa-li"],
    requires_substantiation: false,
    issue: null,
  },
  {
    claim_id: "clm-4",
    statement: "We will confirm your appointment within one business day.",
    risk_tier: "ordinary",
    verification_state: "not_assessed",
    passage_id: "p-cta-1",
    evidence_source_ids: [],
    requires_substantiation: false,
    issue: "Service-level promise was not checked against the booking system.",
  },
];

const SOURCES: EvidenceSource[] = [
  {
    source_id: "src-wa-li",
    label: "official",
    title: "Contractor registration lookup \u2014 Northwind Roofing",
    url: "https://secure.lni.wa.gov/verify/Details.aspx?ContractorID=NORTHRI***",
    publisher: "Washington State Department of Labor & Industries",
    publication_date: "2025-11-02",
    excerpt: "Registration status: Active. Bond: on file. Insurance: on file.",
    accessed_at: "2026-02-10",
  },
  {
    source_id: "src-project-log",
    label: "first_party",
    title: "Northwind Roofing 2025 project log (internal)",
    url: null,
    publisher: "Northwind Roofing",
    publication_date: "2025-12-31",
    excerpt: "1,214 completed roof replacements logged for Whatcom County, 2008\u20132025.",
    accessed_at: null,
  },
  {
    source_id: "src-manual",
    label: "practitioner",
    title: "Asphalt shingle installation manual, section 4 (ventilation and underlayment)",
    url: "https://example-manufacturer.com/install-manual",
    publisher: "Example Shingle Manufacturer",
    publication_date: "2024-06-15",
    excerpt: "Underlayment and balanced ventilation are required for full warranty coverage in wet climates.",
    accessed_at: "2026-02-10",
  },
  {
    source_id: "src-cooling-blog",
    label: "speculative",
    title: "Why reflective shingles pay off (undated blog post)",
    url: "https://example-blog.com/reflective-shingles",
    publisher: "Example Blog",
    publication_date: null,
    excerpt: "\u201cIn some homes, savings can reach 40%.\u201d No methodology or date is provided.",
    accessed_at: "2026-02-10",
  },
];

const TECHNICAL_FLAGS: TechnicalFlag[] = [
  { flag_id: "tf-jsonld", label: "LocalBusiness structured data", severity: "medium", detail: "No JSON-LD block was found in the supplied HTML. Entity attributes may not be machine-readable.", detected: false },
  { flag_id: "tf-canonical", label: "Canonical URL", severity: "low", detail: "No canonical link element was present in the supplied source.", detected: false },
  { flag_id: "tf-hours", label: "Opening hours markup", severity: "medium", detail: "Opening hours are absent from both the page copy and any structured data.", detected: false },
  { flag_id: "tf-images", label: "Project images with alt text", severity: "low", detail: "Three gallery images were supplied without descriptive alt text.", detected: true },
];

const componentScore = (
  score_key: ScoreKey,
  value: number,
  weight: number,
  confidence: ComponentScore["confidence"],
  rationale: string,
  sub_scores: Record<string, number>,
  lost_points_reasons: string[],
  extra: Partial<ComponentScore> = {},
): ComponentScore => ({
  score_key,
  value,
  weight,
  confidence,
  rationale,
  sub_scores,
  lost_points_reasons,
  observed_queries: null,
  simulated_queries: null,
  ...extra,
});

const SCORES: Record<string, ComponentScore> = {
  EOS: componentScore(
    "EOS",
    7.4,
    15,
    "high",
    "The central entity (Northwind Roofing) is named in the first sentence, the service and locale are explicit, and supporting entities are relevant. Attribute completeness drags the score: contact and tenure attributes are missing or vague.",
    {
      central_entity_clarity: 8.5,
      supporting_entity_relevance: 7.5,
      attribute_value_completeness: 5.5,
      intent_and_entity_coverage: 8,
      naming_consistency: 7.5,
      trust_and_authority_entities: 6.5,
      page_type_fit: 8.5,
      semantic_coherence: 9,
    },
    [
      "Required contact_phone attribute is missing.",
      "years_in_business is a vague value (\u201cmany years\u201d).",
      "Trust entities are mentioned without identifiers (registration number).",
    ],
  ),
  ERS: componentScore(
    "ERS",
    6.9,
    15,
    "medium",
    "Capability and geography relationships are stated explicitly, but the causal claim linking reflective shingles to a 40% saving is unsupported, and the warranty relationship is only implied.",
    {
      problem_to_solution: 6.5,
      service_to_outcome: 7,
      process_to_mechanism: 6,
      entity_attribute_clarity: 6.5,
      cause_effect_accuracy: 5,
      claim_to_evidence: 5.5,
      local_and_audience_relationships: 7.5,
      section_continuity: 7.5,
    },
    [
      "One cause-and-effect relationship is unsupported and unqualified.",
      "The workmanship warranty scope is implied rather than stated.",
    ],
  ),
  KGR: componentScore(
    "KGR",
    7.1,
    15,
    "medium",
    "Core category, capability and geography triples are explicit and consistent with the brand entity. The price triple is missing entirely and proof links support only two of seven triples.",
    {
      essential_triples_explicit: 7,
      required_eav_values: 6,
      canonical_naming: 7.5,
      brand_consistency: 8.5,
      type_and_relationship_coherence: 7,
      proof_and_source_links: 5.5,
    },
    [
      "Price triple is missing for a commercial local-service page.",
      "Two of six required EAV attributes are not usable (missing or vague).",
    ],
  ),
  FCS: componentScore(
    "FCS",
    6.2,
    10,
    "low",
    "Weighted coverage of in-scope simulated fan-out queries. Core commercial queries (cost, best contractor) are missing or partial while navigational and locale queries are well covered. No observed queries were available, so this score is hypothesis-based only.",
    {
      core_query_coverage: 5.5,
      common_follow_up_coverage: 6.5,
      edge_query_coverage: 6,
    },
    [
      "All four core cost queries are uncovered.",
      "Decision-support queries (signs you need a new roof, how to choose a contractor) are absent.",
      "Zero observed queries: the score cannot be validated against real demand yet.",
    ],
    { observed_queries: 0, simulated_queries: 18 },
  ),
  PRS: componentScore(
    "PRS",
    8,
    15,
    "high",
    "Passages are short, mostly standalone and use stable entity anchors. Retrievability is limited by two passages that bury the actor and by claim/evidence adjacency on the unsupported numeric claim.",
    {
      answer_first_opening: 7,
      named_subjects_and_anchors: 8.5,
      standalone_comprehension: 8.5,
      claim_evidence_adjacency: 5.5,
      answer_shape_fit: 8,
      priority_information_early: 8.5,
      hierarchy_and_redundancy: 8.5,
    },
    [
      "One passage needs the preceding heading to be understood.",
      "The unsupported claim has no adjacent evidence.",
    ],
  ),
  CWS: componentScore(
    "CWS",
    5.8,
    15,
    "medium",
    "The page contains genuine first-party detail (project volume, warranty term, installation specification) but citation-worthiness is held back by an unsourced numeric claim and the absence of dated, citable local proof.",
    {
      original_first_party_information: 6.5,
      verifiable_evidence_and_sourcing: 4.5,
      information_gain: 6,
      first_hand_expertise: 6,
      claim_precision_and_dates: 4.5,
      attribution_quality: 5.5,
    },
    [
      "The 40% cooling-cost figure is unsourced and undated.",
      "No local case study, dated photo set or measured outcome is published.",
    ],
  ),
  HRS: componentScore(
    "HRS",
    8.3,
    15,
    "high",
    "Plain, readable prose with a clear structure and a single next step. Practical completeness suffers because readers cannot call, book or budget from the page alone.",
    {
      clarity_and_plain_language: 9,
      structure_and_scannability: 8.5,
      practical_completeness: 7,
      relevance_and_no_filler: 8.5,
      tone_and_terminology: 8.5,
      examples_and_decision_support: 7.5,
      conversion_and_next_step_clarity: 8.5,
    },
    [
      "No phone number, so the primary conversion path is incomplete.",
      "No cost or timeline guidance to support a decision.",
    ],
  ),
};

export const NORTHWIND_REPORT: AuditReport = {
  audit_metadata: {
    project_id: "proj-northwind",
    run_id: "run-northwind-2026-02-14",
    page_type: "local_service",
    language: "en",
    central_entity: "Northwind Roofing",
    primary_intent: "local",
    created_at: "2026-02-14T09:12:44Z",
    content_hash: "sha256:9f2c41d7b8e0a3c5f6d9be71aa2c4f8d3e5b6c7a91f2d4e8b0c3a5d7f9e1b2c4",
    score_profile_version: "1.4",
    provider_model: "ollama / llama3.1:8b (local)",
    context_pack_versions: ["northwind-brand-book@1.2.0"],
    assumptions: [
      "The page targets local search intent for a residential roofing contractor in Bellingham, WA.",
      "Search Console and Bing Webmaster Tools are not connected; fan-out queries are simulated hypotheses.",
      "The canonical URL was not fetched; analysis used the supplied Markdown source.",
      "Scores use the commercial-page weighting profile (version 1.4).",
    ],
    warnings: [
      "No observed query data available \u2014 coverage is estimated from simulated queries only.",
      "Deterministic-only stages could not confirm external facts; unverified items are labelled rather than resolved.",
    ],
  },
  gate: {
    status: "pass_with_fixes",
    critical_issues: [],
    noncritical_issues: [
      "A required EAV attribute (contact_phone) is missing and years_in_business is vague for a local-service page.",
      "An unsourced numeric claim (\u201cup to 40%\u201d cooling-cost reduction) must be substantiated or removed before publication.",
      "No cost signal is present despite four core commercial queries about price.",
    ],
  },
  scores: SCORES,
  composite_avr: 7.0,
  entities: ENTITIES,
  eav_rows: EAV_ROWS,
  triples: TRIPLES,
  fanout: FANOUT,
  coverage_rows: COVERAGE_ROWS,
  passage_findings: PASSAGE_FINDINGS,
  passage_skills: NORTHWIND_PASSAGE_SKILLS,
  passages: NORTHWIND_PASSAGES,
  claims: CLAIMS,
  recommendations: RECOMMENDATIONS,
  swot: {
    strengths: [
      "Clear central entity and service definition in the first sentence.",
      "Answer-first opening that names the service area before the fold.",
      "Scannable heading hierarchy with short, self-contained passages.",
    ],
    weaknesses: [
      "Two of six required EAV attributes are missing or vague.",
      "An unsourced numeric claim reduces citation-worthiness and relationship accuracy.",
      "No price, timeline or decision support for commercial queries.",
    ],
    opportunities: [
      "Publish a dated local proof block (project count, before/after photos, one measured outcome).",
      "Add a FAQ covering the missing core fan-out queries (cost, timeline, signs you need a roof).",
      "Add LocalBusiness structured data once contact details and hours are confirmed.",
    ],
    threats: [
      "Competitors publish verified licence numbers and dated case studies that are easier to cite.",
      "Unsourced quantitative claims are quotable and could be surfaced without qualification.",
      "Location coverage is spread across sibling pages without internal links, diluting topical focus.",
    ],
  },
  measurement_plan: [
    { metric: "Coverage of core fan-out queries", source: "Re-run audit (simulated fan-out)", baseline: "core coverage 5.5 / 10", target: "core coverage \u2265 8.0 / 10", check_after: "after the pricing and FAQ updates ship" },
    { metric: "Citation-worthiness", source: "Re-run audit", baseline: "CWS 5.8 / 10", target: "CWS \u2265 7.0 / 10", check_after: "after adding dated sources and a local proof block" },
    { metric: "EAV completeness", source: "EAV matrix", baseline: "2 of 5 applicable attributes explicit", target: "5 of 5 explicit or not applicable", check_after: "after the contact-block update" },
    { metric: "Observed query coverage", source: "Google Search Console (if connected)", baseline: "0 observed queries", target: "connect GSC and re-measure coverage", check_after: "within 28 days of publishing" },
  ],
  sources: SOURCES,
  limitations: [
    "Fan-out queries are simulated hypotheses because no search-console connection was configured.",
    "The live URL was not fetched or rendered; findings reflect the supplied Markdown only.",
    "No external fact-checking provider was configured, so claims are labelled verified/unverified from supplied sources only.",
    "Technical flags are limited to what the supplied source could reveal; Core Web Vitals were not measured.",
  ],
  not_assessed: [
    "Core Web Vitals and field performance",
    "Live rendered-page comparison against the deployed URL",
    "Bing Webmaster Tools query data",
    "Competitor SERP overlap",
  ],
  technical_flags: TECHNICAL_FLAGS,
};
