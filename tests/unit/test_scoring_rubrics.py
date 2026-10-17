"""Unit tests for the low-level rubric calculators (PRD §9.2.A–G).

`ega_scoring.rubrics` exposes the seven core score calculators against raw
schema inputs (entities, triples, coverage rows, parsed documents) instead of
an `AuditRunState`. The formulas must match the state-driven scorers in
`ega_scoring.components`: deterministic, one decimal place, and "not
assessable" must never silently become zero credit where a guard exists.
"""

from __future__ import annotations

import pytest
from ega_parsers.metrics import compute_flesch_reading_ease
from ega_schemas.claims import Claim
from ega_schemas.content import Heading, Link, ParsedDocument, Passage
from ega_schemas.entities import EAVRow, Entity
from ega_schemas.enums import (
    Confidence,
    CoverageStatus,
    EAVStatus,
    EntityKind,
    QueryOrigin,
    TripleStatus,
    TripleType,
)
from ega_schemas.fanout import CoverageRow, FanoutQuery
from ega_schemas.triples import SemanticTriple
from ega_scoring.rubrics import (
    calculate_cws,
    calculate_eos,
    calculate_ers,
    calculate_fcs,
    calculate_hrs,
    calculate_kgr,
    calculate_prs,
)

# ------------------------------------------------------------- test helpers ---


def _entity(
    name: str,
    kind: EntityKind = EntityKind.CONCEPT,
    central: bool = False,
    aliases: list[str] | None = None,
) -> Entity:
    """Build a minimal entity with a deterministic id."""
    return Entity(
        entity_id=f"e-{name}",
        canonical_name=name,
        kind=kind,
        is_central=central,
        aliases=aliases or [],
    )


def _eav(name: str, status: EAVStatus, attribute: str = "founder") -> EAVRow:
    return EAVRow(
        eav_id=f"eav-{name}-{attribute}",
        entity_name=name,
        attribute=attribute,
        value="Ada" if status == EAVStatus.EXPLICIT else None,
        status=status,
    )


def _triple(tid: str, ttype: TripleType, status: TripleStatus) -> SemanticTriple:
    return SemanticTriple(
        triple_id=tid,
        subject="s",
        predicate="p",
        object_="o",
        triple_type=ttype,
        status=status,
    )


def _query(qid: str, origin: QueryOrigin = QueryOrigin.OBSERVED, importance: int = 2) -> FanoutQuery:
    return FanoutQuery(query_id=qid, query_text=f"question {qid}", origin=origin, importance=importance)


def _row(qid: str, status: CoverageStatus, text: str | None = None) -> CoverageRow:
    return CoverageRow(query_id=qid, query_text=text or f"question {qid}", status=status)


def _passage(pid: str, named: bool = False, answer_first: bool = False) -> Passage:
    return Passage(
        passage_id=pid,
        text="Short passage text.",
        word_count=4,
        start_offset=0,
        end_offset=19,
        named_subject=named,
        answer_first=answer_first,
    )


def _doc(
    text: str = "",
    passages: list[Passage] | None = None,
    headings: list[Heading] | None = None,
    links: list[Link] | None = None,
) -> ParsedDocument:
    return ParsedDocument(
        raw_text=text,
        normalized_text=text,
        passages=passages or [],
        headings=headings or [],
        links=links or [],
    )


_EASY_TEXT = (
    "The cat sat on the mat. The dog ran to the park. We like to read books. "
    "It is fun to play games. Kids love simple stories."
)
_DENSE_TEXT = (
    "The implementation of comprehensive organizational transformation "
    "methodologies necessitates institutionalization of cross-functional "
    "collaborative paradigm shifts."
)
_STUFFED_TEXT = (
    "Our CRM software for teams is the best CRM software for sales. "
    "The best CRM software for teams helps you. We built CRM software for "
    "small business. CRM software for enterprises scales."
)

# ------------------------------------------------------------------- FCS ---


def test_fcs_empty_rows_is_zero_with_rationale() -> None:
    """PRD §9.2.D: no coverage rows means no evidence, stated, not silent."""
    result = calculate_fcs([], [_query("q1")])
    assert result.value == 0.0
    assert result.weight == 15.0
    assert "No fan-out query coverage rows available" in result.rationale
    assert result.lost_points_reasons == ["No topical fan-out queries were evaluated."]
    assert result.observed_queries == 0
    assert result.simulated_queries == 0


def test_fcs_all_covered_is_full_credit() -> None:
    rows = [_row("q1", CoverageStatus.COVERED), _row("q2", CoverageStatus.COVERED)]
    queries = [_query("q1", importance=3), _query("q2", importance=1)]
    result = calculate_fcs(rows, queries)
    assert result.value == 10.0
    assert result.lost_points_reasons == []
    assert result.observed_queries == 2
    assert result.simulated_queries == 0


def test_fcs_partial_coverage_halves_importance_credit() -> None:
    """Partial coverage contributes a 0.5 multiplier (PRD §9.2.D)."""
    rows = [_row("q1", CoverageStatus.COVERED), _row("q2", CoverageStatus.PARTIAL)]
    queries = [_query("q1", importance=3), _query("q2", importance=1)]
    result = calculate_fcs(rows, queries)
    # 10 * (3*1.0 + 1*0.5) / 4 = 8.75 -> 8.8
    assert result.value == 8.8
    assert result.lost_points_reasons == ["Query partially answered: 'question q2'"]


def test_fcs_missing_coverage_is_named_in_lost_points() -> None:
    rows = [_row("q1", CoverageStatus.COVERED), _row("q2", CoverageStatus.MISSING, text="gap query")]
    queries = [_query("q1", importance=3), _query("q2", importance=3)]
    result = calculate_fcs(rows, queries)
    # 10 * (3*1.0 + 3*0.0) / 6 = 5.0
    assert result.value == 5.0
    assert result.lost_points_reasons == ["Query missing coverage: 'gap query'"]


def test_fcs_excluded_queries_leave_denominator_and_lost_points() -> None:
    """Excluded/out-of-scope queries are omitted from the denominator (PRD §9.2.D)."""
    rows = [_row("q1", CoverageStatus.COVERED), _row("q2", CoverageStatus.EXCLUDED)]
    queries = [_query("q1", importance=3), _query("q2", importance=1)]
    result = calculate_fcs(rows, queries)
    assert result.value == 10.0
    assert result.lost_points_reasons == []


def test_fcs_confidence_high_only_beyond_five_observed() -> None:
    queries = [_query(f"q{i}") for i in range(6)]
    rows = [_row(f"q{i}", CoverageStatus.COVERED) for i in range(6)]
    assert calculate_fcs(rows, queries).confidence == Confidence.HIGH


def test_fcs_confidence_medium_when_any_query_simulated() -> None:
    queries = [_query("q1"), _query("q2", origin=QueryOrigin.SIMULATED)]
    rows = [_row("q1", CoverageStatus.COVERED), _row("q2", CoverageStatus.COVERED)]
    result = calculate_fcs(rows, queries)
    assert result.confidence == Confidence.MEDIUM
    assert result.simulated_queries == 1


def test_fcs_rows_without_matching_queries_default_importance_two() -> None:
    rows = [_row("q1", CoverageStatus.COVERED)]
    result = calculate_fcs(rows, [])
    assert result.value == 10.0
    assert result.confidence == Confidence.LOW
    assert result.observed_queries == 0
    assert result.simulated_queries == 0


def test_fcs_all_excluded_rows_hit_zero_denominator_guard() -> None:
    """A zero denominator is a stated guard, never a division crash (PRD §9.1).

    `FanoutQuery.importance` is bounded to >= 1, so the only reachable
    zero-denominator path is a row set where every row is excluded: the
    weighted ratio falls back to 0.0 instead of dividing by zero.
    """
    rows = [_row("q1", CoverageStatus.EXCLUDED), _row("q2", CoverageStatus.EXCLUDED)]
    queries = [_query("q1"), _query("q2")]
    result = calculate_fcs(rows, queries)
    assert result.value == 0.0
    assert result.lost_points_reasons == []


# ------------------------------------------------------------------- EOS ---


def test_eos_empty_inventory_is_stated_low_not_silent() -> None:
    result = calculate_eos([], [], None)
    assert result.value == 4.5
    assert result.confidence == Confidence.LOW
    assert result.weight == 15.0
    texts = " ".join(result.lost_points_reasons)
    assert "Central entity is undefined" in texts
    assert "Sparse supporting entity inventory" in texts
    assert "No explicit entity attribute-value (EAV) pairs detected." in texts
    assert "Missing explicit trust/authority entities" in texts


def test_eos_rich_inventory_scores_high_without_lost_points() -> None:
    """PRD §9.2.A full-weight path: central + 5 support + explicit EAVs + trust."""
    entities = [_entity("Acme", EntityKind.ORGANIZATION, central=True, aliases=["Acme Corp"])]
    entities += [_entity(f"support-{i}") for i in range(5)]
    eav_rows = [_eav("Acme", EAVStatus.EXPLICIT, attribute=f"attr{i}") for i in range(3)]
    result = calculate_eos(entities, eav_rows, None)
    assert result.value == 9.1
    assert result.confidence == Confidence.HIGH
    assert result.lost_points_reasons == []
    assert len(result.sub_scores) == 8
    assert result.sub_scores["entity_coverage"] == 8.0  # 5 + 6 * 0.5


def test_eos_keyword_stuffing_detected_from_repeated_phrases() -> None:
    doc = _doc(text=_STUFFED_TEXT)
    entities = [_entity("Acme", EntityKind.ORGANIZATION, central=True, aliases=["Acme Corp"])]
    eav_rows = [_eav("Acme", EAVStatus.EXPLICIT)]
    result = calculate_eos(entities, eav_rows, doc)
    assert result.sub_scores["coherence_no_stuffing"] == 3.0
    assert any("keyword stuffing detected" in r for r in result.lost_points_reasons)


def test_eos_partial_eav_completeness_reports_ratio() -> None:
    entities = [_entity("Acme", central=True), _entity("Beta")]
    eav_rows = [
        _eav("Acme", EAVStatus.EXPLICIT),
        _eav("Beta", EAVStatus.MISSING),
        _eav("Acme", EAVStatus.VAGUE, attribute="founded"),
    ]
    result = calculate_eos(entities, eav_rows, None)
    assert result.sub_scores["eav_completeness"] == 3.3  # 1/3 explicit
    assert "Only 1/3 entity attributes have explicit values." in result.lost_points_reasons


def test_eos_full_eav_completeness_is_ten() -> None:
    eav_rows = [_eav("Acme", EAVStatus.EXPLICIT, attribute=f"attr{i}") for i in range(4)]
    result = calculate_eos([_entity("Acme", central=True)], eav_rows, None)
    assert result.sub_scores["eav_completeness"] == 10.0


# ------------------------------------------------------------------- ERS ---


def test_ers_no_triples_is_floor_with_stated_reason() -> None:
    result = calculate_ers([], [])
    assert result.value == 2.0
    assert result.confidence == Confidence.LOW
    assert result.lost_points_reasons == ["Missing structured subject-predicate-object triples."]


def test_ers_all_explicit_and_diverse_scores_high() -> None:
    triples = [
        _triple("t1", TripleType.CAPABILITY, TripleStatus.EXPLICIT),
        _triple("t2", TripleType.OUTCOME, TripleStatus.EXPLICIT),
        _triple("t3", TripleType.CAUSE_EFFECT, TripleStatus.EXPLICIT),
    ]
    result = calculate_ers(triples, [])
    # ratio 10.0 * 0.6 + diversity 7.5 * 0.4 = 9.0
    assert result.value == 9.0
    assert result.lost_points_reasons == []
    assert result.confidence == Confidence.MEDIUM


def test_ers_mostly_implied_triples_lose_points_twice() -> None:
    triples = [
        _triple("t1", TripleType.CAPABILITY, TripleStatus.EXPLICIT),
        _triple("t2", TripleType.OUTCOME, TripleStatus.EXPLICIT),
        _triple("t3", TripleType.CAPABILITY, TripleStatus.IMPLIED),
        _triple("t4", TripleType.OUTCOME, TripleStatus.IMPLIED),
        _triple("t5", TripleType.CAPABILITY, TripleStatus.IMPLIED),
    ]
    result = calculate_ers(triples, [])
    # ratio 4.0 * 0.6 + diversity 5.0 * 0.4 = 4.4
    assert result.value == 4.4
    texts = " ".join(result.lost_points_reasons)
    assert "Only 2/5 relationships are explicitly stated." in texts
    assert "Narrow relationship variety" in texts


# ------------------------------------------------------------------- KGR ---


def test_kgr_empty_inputs_report_low_readiness() -> None:
    result = calculate_kgr([], [], [])
    assert result.value == 2.9
    assert result.confidence == Confidence.LOW
    assert len(result.lost_points_reasons) == 2
    assert any("Unanchored central subject" in r for r in result.lost_points_reasons)
    assert any("Insufficient explicit predicate triples" in r for r in result.lost_points_reasons)


def test_kgr_rich_graph_scores_high_with_high_confidence() -> None:
    entities = [_entity("Acme", central=True)]
    triples = [_triple(f"t{i}", TripleType.CAPABILITY, TripleStatus.EXPLICIT) for i in range(4)]
    eav_rows = [_eav("Acme", EAVStatus.EXPLICIT, attribute=f"attr{i}") for i in range(3)]
    result = calculate_kgr(triples, eav_rows, entities)
    # 9.0*0.4 + 8.5*0.3 + 9.0*0.3 = 8.85 -> 8.8 (one-decimal rounding)
    assert result.value == 8.8
    assert result.confidence == Confidence.HIGH
    assert result.lost_points_reasons == []


def test_kgr_single_explicit_triple_is_insufficient() -> None:
    entities = [_entity("Acme", central=True)]
    triples = [_triple("t1", TripleType.OUTCOME, TripleStatus.EXPLICIT)]
    result = calculate_kgr(triples, [], entities)
    assert result.sub_scores["central_triples"] == 5.0
    assert result.value == 5.9
    assert result.lost_points_reasons == ["Insufficient explicit predicate triples for KG edge formation."]


# ------------------------------------------------------------------- PRS ---


@pytest.mark.parametrize("doc", [None, _doc(text="")], ids=["none", "empty-doc"])
def test_prs_no_passages_is_floor_with_stated_reason(doc: ParsedDocument | None) -> None:
    result = calculate_prs(doc)
    assert result.value == 2.0
    assert result.confidence == Confidence.LOW
    assert result.lost_points_reasons == ["Empty or unparseable document passages."]


def test_prs_answer_first_named_passages_score_high() -> None:
    doc = _doc(passages=[_passage(f"p{i}", named=True, answer_first=True) for i in range(4)])
    result = calculate_prs(doc)
    # 10*0.4 + 10*0.4 + 8.5*0.2 = 9.7
    assert result.value == 9.7
    assert result.lost_points_reasons == []
    assert result.confidence == Confidence.HIGH


def test_prs_ambiguous_preamble_passages_lose_both_reasons() -> None:
    doc = _doc(passages=[_passage("p0"), _passage("p1")])
    result = calculate_prs(doc)
    # 0*0.4 + 0*0.4 + 5.0*0.2 = 1.0
    assert result.value == 1.0
    texts = " ".join(result.lost_points_reasons)
    assert "2/2 passages open with ambiguous pronouns" in texts
    assert "preamble-heavy; only 0/2 answer intent" in texts


def test_prs_too_few_passages_penalizes_chunking_only() -> None:
    doc = _doc(passages=[_passage("p0", named=True, answer_first=True), _passage("p1", named=True, answer_first=True)])
    result = calculate_prs(doc)
    assert result.sub_scores["passage_chunking"] == 5.0
    # 10*0.4 + 10*0.4 + 5.0*0.2 = 9.0
    assert result.value == 9.0
    assert result.lost_points_reasons == []


# ------------------------------------------------------------------- CWS ---


def test_cws_no_evidence_anywhere_is_stated_low() -> None:
    result = calculate_cws([], None)
    # 3.0*0.4 + 10.0*0.6 = 7.2
    assert result.value == 7.2
    assert "No authoritative external citation links present to anchor factual claims." in result.lost_points_reasons


def test_cws_external_links_and_substantiated_claims_score_full() -> None:
    links = [Link(url=f"https://src{i}.example", anchor_text="src", is_internal=False) for i in range(4)]
    links += [Link(url="/about", anchor_text="about", is_internal=True), Link(url="https://x.example", anchor_text="top", is_anchor=True)]
    claims = [
        Claim(claim_id="c1", statement="A", requires_substantiation=True, evidence_source_ids=["s1"]),
        Claim(claim_id="c2", statement="B", requires_substantiation=False),
    ]
    result = calculate_cws(claims, _doc(links=links))
    assert result.sub_scores["sourcing_and_references"] == 10.0
    assert result.sub_scores["claim_substantiation"] == 10.0
    assert result.value == 10.0
    assert result.lost_points_reasons == []


def test_cws_unverified_claims_reduce_substantiation_subscore() -> None:
    claims = [
        Claim(claim_id=f"c{i}", statement="S", requires_substantiation=True) for i in range(2)
    ]
    links = [Link(url="https://src.example", anchor_text="src", is_internal=False)]
    result = calculate_cws(claims, _doc(links=links))
    # 2.5*0.4 + 4.0*0.6 = 3.4
    assert result.value == 3.4
    assert (
        "2 empirical or comparative claim(s) lack citation or verifiable source."
        in result.lost_points_reasons
    )


def test_cws_substantiation_subscore_has_floor_of_one() -> None:
    claims = [Claim(claim_id=f"c{i}", statement="S", requires_substantiation=True) for i in range(5)]
    result = calculate_cws(claims, None)
    assert result.sub_scores["claim_substantiation"] == 1.0
    # 3.0*0.4 + 1.0*0.6 = 1.8
    assert result.value == 1.8


# ------------------------------------------------------------------- HRS ---


def test_hrs_without_document_is_neutral_not_zero() -> None:
    result = calculate_hrs(None)
    assert result.value == 5.0
    assert result.weight == 10.0
    assert result.confidence == Confidence.LOW
    assert "No document text to calculate readability." in result.rationale


def test_hrs_easy_text_with_headings_scores_high() -> None:
    doc = _doc(text=_EASY_TEXT, headings=[Heading(level=2, text=f"H{i}") for i in range(3)])
    assert compute_flesch_reading_ease(_EASY_TEXT) >= 60.0
    result = calculate_hrs(doc)
    assert result.value == 9.0
    assert result.sub_scores == {"flesch_ease": 9.0, "scannability": 9.0}


def test_hrs_easy_text_without_headings_loses_scannability() -> None:
    result = calculate_hrs(_doc(text=_EASY_TEXT))
    assert result.sub_scores["scannability"] == 3.5
    # 9.0*0.5 + 3.5*0.5 = 6.25 -> 6.2
    assert result.value == 6.2
    assert "Lacks hierarchical subheadings (H2/H3) for human scannability." in result.lost_points_reasons


def test_hrs_single_heading_is_partial_scannability() -> None:
    doc = _doc(text=_EASY_TEXT, headings=[Heading(level=2, text="Only one")])
    result = calculate_hrs(doc)
    # 9.0*0.5 + 6.5*0.5 = 7.75 -> 7.8
    assert result.value == 7.8
    assert result.lost_points_reasons == []


def test_hrs_dense_text_loses_readability_with_flesch_value() -> None:
    assert compute_flesch_reading_ease(_DENSE_TEXT) < 45.0
    doc = _doc(text=_DENSE_TEXT, headings=[Heading(level=2, text=f"H{i}") for i in range(3)])
    result = calculate_hrs(doc)
    # 4.0*0.5 + 9.0*0.5 = 6.5
    assert result.value == 6.5
    assert any("Flesch Reading Ease: 0.0" in r for r in result.lost_points_reasons)
    assert "Flesch Ease: 0.0" in result.rationale
