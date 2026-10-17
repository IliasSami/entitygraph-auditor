"""Individual rubric calculators for EOS, ERS, KGR, FCS, PRS, CWS, and HRS."""

from __future__ import annotations

from typing import Optional

from ega_parsers.metrics import compute_flesch_reading_ease, detect_repeated_phrases
from ega_schemas.claims import Claim
from ega_schemas.content import ParsedDocument
from ega_schemas.entities import EAVRow, Entity
from ega_schemas.enums import (
    Confidence,
    CoverageStatus,
    EAVStatus,
    PageType,
    ScoreKey,
    TripleStatus,
)
from ega_schemas.fanout import CoverageRow, FanoutQuery
from ega_schemas.scores import ComponentScore
from ega_schemas.triples import SemanticTriple


def calculate_fcs(coverage_rows: list[CoverageRow], fanout_queries: list[FanoutQuery]) -> ComponentScore:
    """Fan-out Coverage Score (PRD §9.2.D):

    Formula: FCS = 10 × Σ(importance_i × coverage_i) / Σ(importance_i)
    Excluded / Out of scope queries are omitted from the denominator.
    """
    if not coverage_rows:
        return ComponentScore(
            score_key=ScoreKey.FCS,
            value=0.0,
            weight=15.0,
            confidence=Confidence.LOW,
            rationale="No fan-out query coverage rows available to evaluate.",
            lost_points_reasons=["No topical fan-out queries were evaluated."],
            observed_queries=0,
            simulated_queries=0,
        )

    # Map queries
    query_map = {q.query_id: q for q in fanout_queries}
    observed_count = sum(1 for q in fanout_queries if q.origin == "observed")
    simulated_count = sum(1 for q in fanout_queries if q.origin == "simulated")

    total_weighted_points = 0.0
    total_importance = 0.0
    lost_reasons: list[str] = []

    for row in coverage_rows:
        if row.status == CoverageStatus.EXCLUDED:
            continue

        q = query_map.get(row.query_id)
        importance = q.importance if q else 2
        total_importance += importance

        weight_mult = 0.0
        if row.status == CoverageStatus.COVERED:
            weight_mult = 1.0
        elif row.status == CoverageStatus.PARTIAL:
            weight_mult = 0.5
            lost_reasons.append(f"Query partially answered: '{row.query_text}'")
        elif row.status == CoverageStatus.MISSING:
            weight_mult = 0.0
            lost_reasons.append(f"Query missing coverage: '{row.query_text}'")

        total_weighted_points += float(importance) * weight_mult

    if total_importance <= 0.0:
        fcs_val = 0.0
    else:
        fcs_val = round((10.0 * total_weighted_points) / total_importance, 1)

    confidence = Confidence.HIGH if observed_count > 5 else Confidence.MEDIUM if simulated_count > 0 else Confidence.LOW
    rationale = f"Evaluated {len(coverage_rows)} in-scope queries ({observed_count} observed, {simulated_count} simulated). Score: {fcs_val}/10."

    return ComponentScore(
        score_key=ScoreKey.FCS,
        value=fcs_val,
        weight=15.0,
        confidence=confidence,
        rationale=rationale,
        sub_scores={"weighted_coverage": fcs_val},
        lost_points_reasons=lost_reasons[:5],
        observed_queries=observed_count,
        simulated_queries=simulated_count,
    )


def calculate_eos(
    entities: list[Entity],
    eav_rows: list[EAVRow],
    parsed_doc: Optional[ParsedDocument],
    page_type: PageType = PageType.GENERAL,
) -> ComponentScore:
    """Entity Optimization Score (PRD §9.2.A):

    Evaluates central entity clarity (20%), supporting entities (15%),
    EAV completeness (15%), coverage (15%), naming consistency (10%),
    trust entities (10%), page-type fit (10%), and absence of keyword stuffing (5%).
    """
    sub_scores: dict[str, float] = {}
    lost_reasons: list[str] = []

    # 1. Central entity clarity
    has_central = any(e.is_central for e in entities)
    sub_scores["central_entity_clarity"] = 10.0 if has_central else 2.0
    if not has_central:
        lost_reasons.append("Central entity is undefined or not prominently established.")

    # 2. Supporting entities
    supporting_count = sum(1 for e in entities if not e.is_central)
    if supporting_count >= 5:
        sub_scores["supporting_entities"] = 9.0
    elif supporting_count >= 2:
        sub_scores["supporting_entities"] = 6.5
    else:
        sub_scores["supporting_entities"] = 3.0
        lost_reasons.append(f"Sparse supporting entity inventory ({supporting_count} detected).")

    # 3. EAV Completeness
    if eav_rows:
        explicit_eav = sum(1 for r in eav_rows if r.status == EAVStatus.EXPLICIT)
        eav_ratio = explicit_eav / float(len(eav_rows))
        sub_scores["eav_completeness"] = round(eav_ratio * 10.0, 1)
        if eav_ratio < 0.7:
            lost_reasons.append(f"Only {explicit_eav}/{len(eav_rows)} entity attributes have explicit values.")
    else:
        sub_scores["eav_completeness"] = 4.0
        lost_reasons.append("No explicit entity attribute-value (EAV) pairs detected.")

    # 4. Entity coverage
    sub_scores["entity_coverage"] = min(10.0, 5.0 + len(entities) * 0.5)

    # 5. Naming consistency & disambiguation
    aliases_present = sum(len(e.aliases) for e in entities)
    sub_scores["naming_consistency"] = 8.5 if aliases_present > 0 or has_central else 6.0

    # 6. Trust/Authority entities
    trust_kinds = {"person", "organization", "standard", "regulation", "proof"}
    has_trust = any(e.kind.value in trust_kinds for e in entities)
    sub_scores["trust_authority"] = 9.0 if has_trust else 4.0
    if not has_trust:
        lost_reasons.append("Missing explicit trust/authority entities (organizations, credentials, standards).")

    # 7. Page-type fit
    sub_scores["page_type_fit"] = 8.0

    # 8. Absence of entity/keyword stuffing
    repeated_phrases = []
    if parsed_doc:
        repeated_phrases = detect_repeated_phrases(parsed_doc.normalized_text, n_gram=3, min_count=4)
    if repeated_phrases:
        sub_scores["coherence_no_stuffing"] = 3.0
        lost_reasons.append(f"Potential keyword stuffing detected ({len(repeated_phrases)} repeated 3-gram patterns).")
    else:
        sub_scores["coherence_no_stuffing"] = 10.0

    # Weighted calculation
    weights = {
        "central_entity_clarity": 0.20,
        "supporting_entities": 0.15,
        "eav_completeness": 0.15,
        "entity_coverage": 0.15,
        "naming_consistency": 0.10,
        "trust_authority": 0.10,
        "page_type_fit": 0.10,
        "coherence_no_stuffing": 0.05,
    }

    final_val = sum(sub_scores[k] * weights[k] for k in weights)
    final_val = round(max(0.0, min(10.0, final_val)), 1)

    return ComponentScore(
        score_key=ScoreKey.EOS,
        value=final_val,
        weight=15.0,
        confidence=Confidence.HIGH if entities else Confidence.LOW,
        rationale=f"EOS {final_val}/10 across {len(entities)} entities and {len(eav_rows)} attributes.",
        sub_scores=sub_scores,
        lost_points_reasons=lost_reasons,
    )


def calculate_ers(triples: list[SemanticTriple], eav_rows: list[EAVRow]) -> ComponentScore:
    """Entity Relationship Score (PRD §9.2.B):

    Evaluates explicit predicate connections, problem->solution, capability->outcome,
    and cause->effect triples.
    """
    lost_reasons: list[str] = []
    sub_scores: dict[str, float] = {}

    if not triples:
        return ComponentScore(
            score_key=ScoreKey.ERS,
            value=2.0,
            weight=15.0,
            confidence=Confidence.LOW,
            rationale="No explicit semantic relationship triples found.",
            lost_points_reasons=["Missing structured subject-predicate-object triples."],
        )

    explicit_triples = sum(1 for t in triples if t.status == TripleStatus.EXPLICIT)
    ratio = explicit_triples / float(len(triples))

    # Evaluate triple variety
    types = {t.triple_type for t in triples}
    sub_scores["explicit_triple_ratio"] = round(ratio * 10.0, 1)
    sub_scores["relationship_diversity"] = min(10.0, len(types) * 2.5)

    if ratio < 0.6:
        lost_reasons.append(f"Only {explicit_triples}/{len(triples)} relationships are explicitly stated.")
    if len(types) < 3:
        lost_reasons.append("Narrow relationship variety (e.g. missing problem-solution or cause-effect links).")

    final_val = round((sub_scores["explicit_triple_ratio"] * 0.6) + (sub_scores["relationship_diversity"] * 0.4), 1)

    return ComponentScore(
        score_key=ScoreKey.ERS,
        value=final_val,
        weight=15.0,
        confidence=Confidence.MEDIUM,
        rationale=f"ERS {final_val}/10 based on {len(triples)} triples ({explicit_triples} explicit).",
        sub_scores=sub_scores,
        lost_points_reasons=lost_reasons,
    )


def calculate_kgr(triples: list[SemanticTriple], eav_rows: list[EAVRow], entities: list[Entity]) -> ComponentScore:
    """Knowledge-Graph Readiness Score (PRD §9.2.C):

    Measures disambiguation, EAV values, and triple clarity for semantic graphs.
    """
    lost_reasons: list[str] = []
    sub_scores: dict[str, float] = {}

    has_central = any(e.is_central for e in entities)
    central_triples = sum(1 for t in triples if t.status == TripleStatus.EXPLICIT)

    sub_scores["central_triples"] = 9.0 if central_triples >= 3 else (5.0 if central_triples >= 1 else 2.0)
    sub_scores["eav_readiness"] = 8.5 if len(eav_rows) >= 3 else 4.0
    sub_scores["disambiguation"] = 9.0 if has_central else 3.0

    if not has_central:
        lost_reasons.append("Unanchored central subject inhibits knowledge graph node generation.")
    if central_triples < 2:
        lost_reasons.append("Insufficient explicit predicate triples for KG edge formation.")

    final_val = round((sub_scores["central_triples"] * 0.4) + (sub_scores["eav_readiness"] * 0.3) + (sub_scores["disambiguation"] * 0.3), 1)

    return ComponentScore(
        score_key=ScoreKey.KGR,
        value=final_val,
        weight=15.0,
        confidence=Confidence.HIGH if has_central else Confidence.LOW,
        rationale=f"KGR {final_val}/10: {central_triples} explicit triples, {len(eav_rows)} attributes.",
        sub_scores=sub_scores,
        lost_points_reasons=lost_reasons,
    )


def calculate_prs(parsed_doc: Optional[ParsedDocument]) -> ComponentScore:
    """Passage Retrievability Score (PRD §9.2.E):

    Measures answer-first opening, named subject anchors, self-containedness, and answer shapes.
    """
    lost_reasons: list[str] = []
    sub_scores: dict[str, float] = {}

    if not parsed_doc or not parsed_doc.passages:
        return ComponentScore(
            score_key=ScoreKey.PRS,
            value=2.0,
            weight=15.0,
            confidence=Confidence.LOW,
            rationale="No retrievable passages available.",
            lost_points_reasons=["Empty or unparseable document passages."],
        )

    passages = parsed_doc.passages
    total_p = len(passages)
    named_subjects = sum(1 for p in passages if p.named_subject)
    answer_first_count = sum(1 for p in passages if p.answer_first)

    named_ratio = named_subjects / float(total_p)
    answer_first_ratio = answer_first_count / float(total_p)

    sub_scores["named_subject_anchors"] = round(named_ratio * 10.0, 1)
    sub_scores["answer_first_openings"] = round(answer_first_ratio * 10.0, 1)
    sub_scores["passage_chunking"] = 8.5 if 3 <= total_p <= 40 else 5.0

    if named_ratio < 0.6:
        lost_reasons.append(f"{total_p - named_subjects}/{total_p} passages open with ambiguous pronouns or deictic references.")
    if answer_first_ratio < 0.4:
        lost_reasons.append(f"Passages are preamble-heavy; only {answer_first_count}/{total_p} answer intent in the first sentence.")

    final_val = round((sub_scores["named_subject_anchors"] * 0.4) + (sub_scores["answer_first_openings"] * 0.4) + (sub_scores["passage_chunking"] * 0.2), 1)

    return ComponentScore(
        score_key=ScoreKey.PRS,
        value=final_val,
        weight=15.0,
        confidence=Confidence.HIGH,
        rationale=f"PRS {final_val}/10 across {total_p} passages ({named_subjects} named subjects, {answer_first_count} answer-first).",
        sub_scores=sub_scores,
        lost_points_reasons=lost_reasons,
    )


def calculate_cws(claims: list[Claim], parsed_doc: Optional[ParsedDocument]) -> ComponentScore:
    """Citation-Worthiness / Information Gain Score (PRD §9.2.F):

    Measures verifiable evidence, first-party data, quotes, and lack of unsubstantiated claims.
    """
    lost_reasons: list[str] = []
    sub_scores: dict[str, float] = {}

    external_links = [link for link in (parsed_doc.links if parsed_doc else []) if not link.is_internal and not link.is_anchor]
    
    # Check claim substantiation
    unverified_claims = [c for c in claims if c.requires_substantiation and not c.evidence_source_ids]
    
    sub_scores["sourcing_and_references"] = min(10.0, len(external_links) * 2.5) if external_links else 3.0
    sub_scores["claim_substantiation"] = 10.0 if not unverified_claims else max(1.0, 10.0 - (len(unverified_claims) * 3.0))

    if unverified_claims:
        lost_reasons.append(f"{len(unverified_claims)} empirical or comparative claim(s) lack citation or verifiable source.")
    if not external_links:
        lost_reasons.append("No authoritative external citation links present to anchor factual claims.")

    final_val = round((sub_scores["sourcing_and_references"] * 0.4) + (sub_scores["claim_substantiation"] * 0.6), 1)

    return ComponentScore(
        score_key=ScoreKey.CWS,
        value=final_val,
        weight=15.0,
        confidence=Confidence.MEDIUM,
        rationale=f"CWS {final_val}/10: {len(external_links)} citations, {len(claims)} claims tracked.",
        sub_scores=sub_scores,
        lost_points_reasons=lost_reasons,
    )


def calculate_hrs(parsed_doc: Optional[ParsedDocument]) -> ComponentScore:
    """Human Readability & Utility Score (PRD §9.2.G):

    Evaluates Flesch ease, structural scannability (headings, bullet points), and clarity.
    """
    lost_reasons: list[str] = []
    sub_scores: dict[str, float] = {}

    if not parsed_doc:
        return ComponentScore(
            score_key=ScoreKey.HRS,
            value=5.0,
            weight=10.0,
            confidence=Confidence.LOW,
            rationale="No document text to calculate readability.",
        )

    flesch = compute_flesch_reading_ease(parsed_doc.normalized_text)
    
    # Flesch ease 60-70 is standard plain English, 50-60 is acceptable, <40 is overly dense
    if flesch >= 60.0:
        flesch_score = 9.0
    elif flesch >= 45.0:
        flesch_score = 7.5
    else:
        flesch_score = 4.0
        lost_reasons.append(f"Text is overly dense or convoluted (Flesch Reading Ease: {flesch}/100).")

    # Scannability: headings presence
    h_count = len(parsed_doc.headings)
    if h_count >= 3:
        scan_score = 9.0
    elif h_count >= 1:
        scan_score = 6.5
    else:
        scan_score = 3.5
        lost_reasons.append("Lacks hierarchical subheadings (H2/H3) for human scannability.")

    sub_scores["flesch_ease"] = flesch_score
    sub_scores["scannability"] = scan_score

    final_val = round((flesch_score * 0.5) + (scan_score * 0.5), 1)

    return ComponentScore(
        score_key=ScoreKey.HRS,
        value=final_val,
        weight=10.0,
        confidence=Confidence.HIGH,
        rationale=f"HRS {final_val}/10 (Flesch Ease: {flesch}, {h_count} subheadings).",
        sub_scores=sub_scores,
        lost_points_reasons=lost_reasons,
    )
