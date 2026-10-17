"""Unit tests for ega_scoring engine and rubrics."""

from ega_parsers import DocumentParser
from ega_schemas import (
    Claim,
    ClaimRiskTier,
    CoverageRow,
    CoverageStatus,
    EAVRow,
    EAVStatus,
    Entity,
    EntityKind,
    FanoutQuery,
    GateStatus,
    PageType,
    ScoreKey,
    SemanticTriple,
    TripleStatus,
    TripleType,
    VerificationState,
)
from ega_scoring import ScoringEngine, calculate_fcs


def test_fcs_formula_calculation():
    # Formula: FCS = 10 × Σ(importance_i × coverage_i) / Σ(importance_i)
    # Query 1: importance 3, status COVERED (1.0) -> points = 3.0
    # Query 2: importance 2, status PARTIAL (0.5) -> points = 1.0
    # Query 3: importance 1, status MISSING (0.0) -> points = 0.0
    # Total points = 4.0. Total importance = 6.0.
    # FCS = 10 * 4.0 / 6.0 = 6.666... -> 6.7
    queries = [
        FanoutQuery(query_id="q1", query_text="What is Acme?", importance=3),
        FanoutQuery(query_id="q2", query_text="How much does it cost?", importance=2),
        FanoutQuery(query_id="q3", query_text="Is it open source?", importance=1),
    ]
    rows = [
        CoverageRow(query_id="q1", query_text="What is Acme?", status=CoverageStatus.COVERED),
        CoverageRow(query_id="q2", query_text="How much does it cost?", status=CoverageStatus.PARTIAL),
        CoverageRow(query_id="q3", query_text="Is it open source?", status=CoverageStatus.MISSING),
    ]
    score = calculate_fcs(rows, queries)
    assert score.value == 6.7
    assert score.score_key == ScoreKey.FCS


def test_gate_evaluator_triggers_on_high_stakes_danger():
    claims = [
        Claim(
            claim_id="c1",
            statement="This secret herb 100% cures cancer without chemotherapy.",
            risk_tier=ClaimRiskTier.HIGH_STAKES,
            verification_state=VerificationState.UNVERIFIED,
            requires_substantiation=True,
        )
    ]
    doc = DocumentParser.parse("This secret herb 100% cures cancer without chemotherapy.")
    card = ScoringEngine.evaluate(
        entities=[],
        eav_rows=[],
        triples=[],
        fanout_queries=[],
        coverage_rows=[],
        claims=claims,
        parsed_doc=doc,
    )
    assert card.gate.status == GateStatus.FAIL
    assert any("Critical Compliance Trigger" in issue for issue in card.gate.critical_issues)


def test_scoring_engine_full_run():
    doc = DocumentParser.parse("""# Acme Analytics Engine
Acme Analytics Engine provides real-time streaming database auditing for enterprise platforms.

## Core Capabilities
It processes over 100,000 events per second with sub-millisecond latency.
Our enterprise SLA guarantees 99.99% availability.
""")
    entities = [
        Entity(entity_id="e1", canonical_name="Acme Analytics Engine", is_central=True, kind=EntityKind.PRODUCT_SERVICE),
        Entity(entity_id="e2", canonical_name="enterprise platforms", kind=EntityKind.AUDIENCE),
    ]
    eav_rows = [
        EAVRow(eav_id="eav1", entity_name="Acme Analytics Engine", attribute="throughput", value="100,000 events/sec", status=EAVStatus.EXPLICIT),
        EAVRow(eav_id="eav2", entity_name="Acme Analytics Engine", attribute="sla", value="99.99%", status=EAVStatus.EXPLICIT),
    ]
    triples = [
        SemanticTriple(triple_id="t1", subject="Acme Analytics Engine", predicate="provides", object_="database auditing", status=TripleStatus.EXPLICIT, triple_type=TripleType.CAPABILITY)
    ]

    card = ScoringEngine.evaluate(
        entities=entities,
        eav_rows=eav_rows,
        triples=triples,
        fanout_queries=[],
        coverage_rows=[],
        claims=[],
        parsed_doc=doc,
        page_type=PageType.SERVICE,
    )

    assert card.scores[ScoreKey.EOS.value].value > 6.0
    assert card.avr is not None
    assert card.avr > 0.0
    assert card.gate.status in (GateStatus.PASS, GateStatus.NOT_CONFIGURED)
    assert card.gate.publishable is True
