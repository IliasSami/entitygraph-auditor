"""Shared realistic AuditReport fixtures for export/compare unit tests.

Three reports model the same audited page over time:
- ``build_report_a()`` — baseline run: gate FAIL, profile 1.0, EAV gaps.
- ``build_report_b()`` — improved candidate, same like-for-like dimensions.
- ``build_report_c()`` — run under a different profile/provider/context pack.

Content deliberately includes non-ASCII strings ("café", "ঢাকা") and an XSS
payload so renderers can be tested for round-trip and escaping.
"""

from ega_schemas import (
    AnswerShape,
    AuditMetadata,
    AuditReport,
    Claim,
    ClaimRiskTier,
    ComponentScore,
    Confidence,
    CoverageRow,
    CoverageStatus,
    EAVRow,
    EAVStatus,
    Entity,
    EntityKind,
    EntityOccurrence,
    FanoutQuery,
    Finding,
    FindingHow,
    FindingWhere,
    FindingWhy,
    GateResult,
    GateStatus,
    IntentClass,
    PageType,
    QueryOrigin,
    QueryScope,
    QuerySource,
    RecommendationStatus,
    Scorecard,
    SemanticTriple,
    Severity,
    SwotAnalysis,
    TripleStatus,
    TripleType,
    VerificationState,
)

# ``SourceCitation`` is defined in ``ega_schemas.report`` but not (yet)
# re-exported from the package root; import it from its defining module so we
# do not have to edit the shared schema contract.
from ega_schemas.report import SourceCitation  # noqa: E402

XSS_PAYLOAD = "<script>alert(1)</script>"


def _occurrences(entity_id: str, count: int) -> list[EntityOccurrence]:
    return [
        EntityOccurrence(
            passage_id=f"{entity_id}-p{i}",
            start_offset=i * 10,
            end_offset=i * 10 + 8,
            sentence="Sample sentence.",
        )
        for i in range(count)
    ]


def _metadata(run_id: str, **overrides) -> AuditMetadata:
    data = dict(
        project_id="proj-cafe",
        run_id=run_id,
        page_type=PageType.ARTICLE,
        language="en",
        central_entity="Café Noir Roastery",
        primary_intent=IntentClass.INFORMATIONAL,
        created_at="2026-10-01T09:30:00Z",
        content_hash="sha256:aaaa1111",
        score_profile_version="1.0",
        provider_model="local/llama-3.1",
        context_pack_versions=["brand-pack@1.0"],
        assumptions=["Assumed audience: specialty-coffee enthusiasts."],
        warnings=["Source fetch skipped; audit ran on supplied text only."],
        skipped_stages=["source_fetch"],
    )
    data.update(overrides)
    return AuditMetadata(**data)


def _entities_a() -> list[Entity]:
    return [
        Entity(
            entity_id="e1",
            canonical_name="Café Noir Roastery",
            kind=EntityKind.CENTRAL,
            salience=0.9,
            is_central=True,
            aliases=["Café Noir", "the roastery"],
            occurrences=_occurrences("e1", 3),
        ),
        Entity(
            entity_id="e2",
            canonical_name="single origin coffee",
            kind=EntityKind.CONCEPT,
            salience=0.7,
            occurrences=_occurrences("e2", 4),
        ),
        Entity(
            entity_id="e3",
            canonical_name="ঢাকা",
            kind=EntityKind.LOCATION,
            salience=0.6,
            aliases=["Dhaka"],
            occurrences=_occurrences("e3", 2),
        ),
        Entity(
            entity_id="e4",
            canonical_name="cold brew",
            kind=EntityKind.CONCEPT,
            salience=0.5,
            occurrences=_occurrences("e4", 3),
        ),
        Entity(
            entity_id="e5",
            canonical_name="barista community",
            kind=EntityKind.AUDIENCE,
            salience=0.4,
            occurrences=_occurrences("e5", 1),
        ),
        Entity(
            entity_id="e6",
            canonical_name="Old Vendor & Co",
            kind=EntityKind.ORGANIZATION,
            salience=0.2,
            occurrences=_occurrences("e6", 1),
        ),
    ]


def _eav_a() -> list[EAVRow]:
    return [
        EAVRow(
            eav_id="eav-1",
            entity_name="Café Noir Roastery",
            attribute="founding_year",
            value="2011",
            status=EAVStatus.EXPLICIT,
            evidence_excerpt="Founded in 2011 as a micro-roastery.",
        ),
        EAVRow(
            eav_id="eav-2",
            entity_name="Café Noir Roastery",
            attribute="price_range",
            value=None,
            status=EAVStatus.MISSING,
            notes="Add a price-tier sentence near the intro.",
            is_required_by_page_type=True,
        ),
        EAVRow(
            eav_id="eav-3",
            entity_name="single origin coffee",
            attribute="definition",
            value="beans traceable to one farm",
            status=EAVStatus.VAGUE,
            evidence_excerpt="Traceable beans, supposedly.",
        ),
        EAVRow(
            eav_id="eav-4",
            entity_name="Café Noir Roastery",
            attribute="flagship_location",
            value="Dhaka",
            status=EAVStatus.EXPLICIT,
            evidence_excerpt="Our flagship roastery sits in ঢাকা.",
        ),
        EAVRow(
            eav_id="eav-5",
            entity_name="cold brew",
            attribute="serving_temperature",
            value="4 °C",
            status=EAVStatus.NOT_APPLICABLE,
            evidence_excerpt="Serve over ice.",
        ),
    ]


def _triples_a() -> list[SemanticTriple]:
    return [
        SemanticTriple(
            triple_id="t1",
            subject="Café Noir Roastery",
            predicate="sells",
            object_="single origin coffee",
            triple_type=TripleType.CATEGORY,
            status=TripleStatus.EXPLICIT,
            evidence_excerpt="We sell single origin coffee.",
        ),
        SemanticTriple(
            triple_id="t2",
            subject="Café Noir Roastery",
            predicate="offers",
            object_="cold brew",
            triple_type=TripleType.CAPABILITY,
            status=TripleStatus.EXPLICIT,
            evidence_excerpt="Every morning we pour cold brew.",
        ),
        SemanticTriple(
            triple_id="t3",
            subject="Café Noir Roastery",
            predicate="based_in",
            object_="ঢাকা",
            triple_type=TripleType.GEOGRAPHY,
            status=TripleStatus.EXPLICIT,
            evidence_excerpt="The roastery is based in ঢাকা.",
        ),
        SemanticTriple(
            triple_id="t4",
            subject="Café Noir Roastery",
            predicate="roasts_in_batches_on",
            object_="5 kg drum roaster",
            triple_type=TripleType.PROCESS,
            status=TripleStatus.IMPLIED,
        ),
        SemanticTriple(
            triple_id="t5",
            subject="cold brew",
            predicate="reduces",
            object_="perceived bitterness",
            triple_type=TripleType.OUTCOME,
            status=TripleStatus.MISSING,
        ),
    ]


def _fanout_a() -> list[FanoutQuery]:
    return [
        FanoutQuery(
            query_id="q1",
            query_text="What is single origin coffee?",
            origin=QueryOrigin.OBSERVED,
            source=QuerySource.GSC,
            importance=3,
        ),
        FanoutQuery(
            query_id="q2",
            query_text="How much does Café Noir charge?",
            origin=QueryOrigin.SIMULATED,
            source=QuerySource.GENERATED,
            importance=2,
            answer_shape=AnswerShape.PRICING_FACT,
        ),
        FanoutQuery(
            query_id="q3",
            query_text="Where is the roastery located?",
            origin=QueryOrigin.OBSERVED,
            source=QuerySource.BING,
            importance=2,
        ),
        FanoutQuery(
            query_id="q4",
            query_text="Is cold brew stronger than espresso?",
            origin=QueryOrigin.SIMULATED,
            source=QuerySource.GENERATED,
            importance=2,
        ),
        FanoutQuery(
            query_id="q5",
            query_text="Does Café Noir ship to Europe?",
            origin=QueryOrigin.SIMULATED,
            source=QuerySource.TOPICAL_MAP,
            importance=1,
        ),
        FanoutQuery(
            query_id="q6",
            query_text="What are roastery tour hours?",
            origin=QueryOrigin.SIMULATED,
            source=QuerySource.GENERATED,
            importance=1,
            scope=QueryScope.OUT_OF_SCOPE,
        ),
        FanoutQuery(
            query_id="q7",
            query_text="Who founded Café Noir?",
            origin=QueryOrigin.OBSERVED,
            source=QuerySource.USER_BRIEF,
            importance=3,
        ),
        FanoutQuery(
            query_id="q8",
            query_text="Is Café Noir Fairtrade certified?",
            origin=QueryOrigin.SIMULATED,
            source=QuerySource.GENERATED,
            importance=2,
        ),
    ]


def _coverage_a() -> list[CoverageRow]:
    return [
        CoverageRow(
            query_id="q1",
            query_text="What is single origin coffee?",
            status=CoverageStatus.COVERED,
            coverage_score=1.0,
        ),
        CoverageRow(
            query_id="q2",
            query_text="How much does Café Noir charge?",
            status=CoverageStatus.MISSING,
            coverage_score=0.0,
            gap_reason="No pricing evidence on the page.",
        ),
        CoverageRow(
            query_id="q3",
            query_text="Where is the roastery located?",
            status=CoverageStatus.COVERED,
            coverage_score=1.0,
        ),
        CoverageRow(
            query_id="q4",
            query_text="Is cold brew stronger than espresso?",
            status=CoverageStatus.PARTIAL,
            coverage_score=0.5,
            gap_reason="Caffeine numbers are never compared.",
        ),
        CoverageRow(
            query_id="q5",
            query_text="Does Café Noir ship to Europe?",
            status=CoverageStatus.MISSING,
            coverage_score=0.0,
            gap_reason="Shipping policy absent.",
        ),
        CoverageRow(
            query_id="q6",
            query_text="What are roastery tour hours?",
            status=CoverageStatus.EXCLUDED,
            coverage_score=0.0,
            destination_page="/events/roastery-tours",
        ),
        CoverageRow(
            query_id="q7",
            query_text="Who founded Café Noir?",
            status=CoverageStatus.COVERED,
            coverage_score=1.0,
        ),
        CoverageRow(
            query_id="q8",
            query_text="Is Café Noir Fairtrade certified?",
            status=CoverageStatus.PARTIAL,
            coverage_score=0.5,
            gap_reason="Certification is not stated.",
        ),
    ]


def _passage_findings() -> list[Finding]:
    return [
        Finding(
            finding_id="pf-1",
            category="passage_retrievability",
            severity=Severity.HIGH,
            title="Intro buries the answer",
            what="The opening paragraph delays the definition of the roastery.",
            where=FindingWhere(
                passage_id="p1",
                excerpt="At Café Noir, mornings start with a café au lait and a slow pour-over.",
            ),
            why=FindingWhy(intent_or_query="What is single origin coffee?", layer="passage"),
            how=FindingHow(
                suggested_rewrite=(
                    "Café Noir Roastery is a micro-roastery in ঢাকা that sells"
                    " single-origin coffee."
                ),
                verification_condition="The first sentence answers the primary query.",
            ),
            evidence=["Definition appears in paragraph three."],
            priority_score=7.5,
        ),
        Finding(
            finding_id="pf-2",
            category="passage_audit",
            severity=Severity.MEDIUM,
            title="Brew guide never states steep time",
            what="Readers cannot extract the steep time from the brew guide.",
            where=FindingWhere(passage_id="p4", excerpt=XSS_PAYLOAD + " The brew guide never states steep time."),
            how=FindingHow(suggested_rewrite="Steep coarse grounds for 12 to 16 hours."),
            evidence=["No duration value in the brew section."],
            priority_score=6.0,
        ),
        Finding(
            finding_id="pf-3",
            category="passage_audit",
            severity=Severity.LOW,
            title="Opening hours lack a concrete time",
            what="Multi-line\nwhat text with, comma about opening hours near ঢাকা.",
            where=FindingWhere(passage_id="p7", excerpt="Our flagship counter in ঢাকা opens at 7 a.m."),
            evidence=["Hours described as 'early' without a value."],
            priority_score=2.5,
        ),
        Finding(
            finding_id="pf-4",
            category="style",
            severity=Severity.INFO,
            title="Avoid unverifiable superlatives in the closing",
            what="The closing paragraph leans on superlatives.",
            where=FindingWhere(passage_id="p9", excerpt="The best coffee in the whole wide city."),
            evidence=["Superlative without a source."],
            priority_score=1.5,
        ),
    ]


def _claims_a() -> list[Claim]:
    return [
        Claim(
            claim_id="c1",
            statement="The roastery produces 12 tons of green coffee every year.",
            risk_tier=ClaimRiskTier.HIGH_STAKES,
            verification_state=VerificationState.UNVERIFIED,
            requires_substantiation=True,
            evidence_source_ids=["src-1"],
        ),
        Claim(
            claim_id="c2",
            statement="Café Noir sources beans from Ethiopian farmers.",
            risk_tier=ClaimRiskTier.ORDINARY,
            verification_state=VerificationState.VERIFIED,
            evidence_source_ids=["src-1"],
        ),
        Claim(
            claim_id="c3",
            statement="Single origin coffee comes from one farm.",
            risk_tier=ClaimRiskTier.ORDINARY,
            verification_state=VerificationState.NOT_ASSESSED,
        ),
        Claim(
            claim_id="c4",
            statement="Roastery tours run every day of the week.",
            risk_tier=ClaimRiskTier.ORDINARY,
            verification_state=VerificationState.VERIFIED,
            evidence_source_ids=["src-2"],
        ),
    ]


def _sources() -> list[SourceCitation]:
    return [
        SourceCitation(
            source_id="src-1",
            title="Café Noir official about page",
            url="https://example.com/about",
            publisher="Café Noir Roastery",
            access_date="2026-09-30T12:00:00Z",
            verification_state="official",
        ),
        SourceCitation(
            source_id="src-2",
            title="Dhaka coffee market report",
            url="https://example.org/report",
            publisher="Dhaka Coffee Institute",
            access_date="2026-09-28T08:00:00Z",
            verification_state="measured_study",
        ),
    ]


def _recommendations_a() -> list[Finding]:
    return [
        Finding(
            finding_id="rec-1",
            category="eav_gap",
            severity=Severity.HIGH,
            title="State price range near first mention",
            what="The page never states a price range for the roastery's coffee.",
            where=FindingWhere(section_id="intro", excerpt="Paragraph two."),
            why=FindingWhy(entity="Café Noir Roastery", attribute="price_range", eav_status="missing"),
            how=FindingHow(
                suggested_rewrite="Cups sit in the €€ mid-range; bags start at €14.",
                verification_condition="A price tier string appears in the first section.",
            ),
            evidence=["EAV price_range status: missing."],
            impact=5,
            confidence_numeric=4,
            effort=2,
            priority_score=10.0,
        ),
        Finding(
            finding_id="rec-2",
            category="terms_lexicon",
            severity=Severity.MEDIUM,
            title="Replace 'best in Dhaka' superlatives with verifiable sourcing facts",
            what="Unverifiable superlatives weaken citation-worthiness.",
            where=FindingWhere(section_id="closing"),
            how=FindingHow(
                suggested_rewrite="Replace with 'roasted in ঢাকা since 2011'.",
                verification_condition="No un-sourced superlative remains.",
            ),
            impact=3,
            confidence_numeric=4,
            effort=2,
            priority_score=6.0,
        ),
        Finding(
            finding_id="rec-3",
            category="internal_link",
            severity=Severity.LOW,
            title="Link the glossary definition of single origin coffee",
            what="The term is used without linking to its glossary entry.",
            where=FindingWhere(section_id="body"),
            how=FindingHow(
                implementation_steps=["Locate the term", "Add the glossary link"],
                verification_condition="The glossary link resolves (200).",
            ),
            impact=2,
            confidence_numeric=4,
            effort=1,
            priority_score=8.0,
            status=RecommendationStatus.OPEN,
        ),
        Finding(
            finding_id="rec-4",
            category="page_type",
            severity=Severity.MEDIUM,
            title="Add an FAQ section for long-tail article queries",
            what="Article pages convert poorly to long-tail without an FAQ block.",
            where=FindingWhere(section_id="end"),
            why=FindingWhy(layer="page_type"),
            how=FindingHow(
                verification_condition="An FAQ heading exists with at least three Q/A pairs.",
            ),
            impact=4,
            confidence_numeric=3,
            effort=2,
            priority_score=6.0,
        ),
        Finding(
            finding_id="rec-5",
            category="fanout_coverage",
            severity=Severity.MEDIUM,
            title="Include a shipping-answer block in the FAQ",
            what="The shipping query is entirely uncovered.",
            where=FindingWhere(section_id="faq"),
            why=FindingWhy(intent_or_query="Does Café Noir ship to Europe?"),
            how=FindingHow(
                verification_condition="The shipping question has a direct answer sentence.",
            ),
            impact=3,
            confidence_numeric=3,
            effort=2,
            priority_score=4.5,
        ),
    ]


def _scores_a() -> dict[str, ComponentScore]:
    return {
        "EOS": ComponentScore(
            score_key="EOS", value=6.0, weight=15, confidence=Confidence.MEDIUM,
            rationale="Central entity clear; attribute coverage thin.",
        ),
        "ERS": ComponentScore(
            score_key="ERS", value=5.5, weight=15, confidence=Confidence.MEDIUM,
            rationale="Key relationships present but one outcome triple missing.",
        ),
        "KGR": ComponentScore(
            score_key="KGR", value=6.2, weight=10, confidence=Confidence.LOW,
            rationale="Naming consistent; required EAV gaps remain.",
        ),
        "FCS": ComponentScore(
            score_key="FCS", value=4.0, weight=15, confidence=Confidence.LOW,
            rationale="Pricing and shipping queries uncovered.",
            observed_queries=3, simulated_queries=5,
        ),
        "PRS": ComponentScore(
            score_key="PRS", value=7.0, weight=15, confidence=Confidence.HIGH,
            rationale="Passages mostly retrievable; intro buries the definition.",
        ),
        "CWS": ComponentScore(
            score_key="CWS", value=5.0, weight=20, confidence=Confidence.MEDIUM,
            rationale="Limited first-party data; one unverified numeric claim.",
        ),
        "HRS": ComponentScore(
            score_key="HRS", value=7.5, weight=10, confidence=Confidence.HIGH,
            rationale="Readable structure, minor filler.",
        ),
        "TRUST": ComponentScore(
            score_key="TRUST", value=4.0, weight=5, confidence=Confidence.NOT_ASSESSED,
            rationale="Not assessed: no author or trust signals in source text.",
        ),
    }


def _swot_a() -> SwotAnalysis:
    return SwotAnalysis(
        strengths=[
            "Clear answer-first definition in the intro",
            "Consistent canonical naming of the brand",
            "Concrete brew temperatures and ratios",
        ],
        weaknesses=["No pricing evidence", "Shipping question unanswered", "No author signals"],
        opportunities=["FAQ block for long-tail queries", "First-party harvest data"],
        threats=["Competitor pages publish price tables", "Unverified numeric claims"],
    )


def _measurement_plan() -> list[dict]:
    return [
        {"metric": "Brand mentions in AI answers", "cadence": "weekly", "engine": "ChatGPT"},
        {"metric": "Citation presence", "cadence": "monthly", "engine": "Perplexity"},
        {"metric": "Coverage of core fan-out queries", "cadence": "per publish", "engine": "n/a"},
    ]


def build_report_a() -> AuditReport:
    """Baseline run: gate FAIL, profile 1.0, several EAV/coverage gaps."""
    return AuditReport(
        audit_metadata=_metadata("run-a"),
        gate=GateResult(
            status=GateStatus.FAIL,
            critical_issues=["Fabricated statistic in intro", "Prohibited cure claim"],
            noncritical_issues=["No FAQ section for long-tail questions"],
        ),
        scores=Scorecard(
            scores=_scores_a(),
            avr=5.9,
            profile_name="editorial_default",
            profile_version="1.0",
        ),
        composite_avr=5.9,
        entities=_entities_a(),
        eav_rows=_eav_a(),
        triples=_triples_a(),
        fanout=_fanout_a(),
        coverage_rows=_coverage_a(),
        passage_findings=_passage_findings(),
        claims=_claims_a(),
        recommendations=_recommendations_a(),
        swot=_swot_a(),
        measurement_plan=_measurement_plan(),
        sources=_sources(),
        limitations=["Only the supplied text was audited; no live URL fetch."],
        not_assessed=["Local pack comparison (no local context pack)."],
    )


def build_report_b() -> AuditReport:
    """Improved candidate: gate PASS, same profile/page type/provider/context packs."""
    entities = _entities_a()[:5]  # e6 "Old Vendor & Co" removed
    entities[0] = entities[0].model_copy(update={"occurrences": _occurrences("e1", 5)})
    entities[1] = entities[1].model_copy(update={"is_central": True})
    entities[3] = entities[3].model_copy(update={"kind": EntityKind.PRODUCT_SERVICE})
    entities.append(
        Entity(
            entity_id="e7",
            canonical_name="Roastery Tours",
            kind=EntityKind.PRODUCT_SERVICE,
            salience=0.5,
            occurrences=_occurrences("e7", 2),
        )
    )
    eav = _eav_a()
    eav[1] = eav[1].model_copy(
        update={
            "value": "€€",
            "status": EAVStatus.EXPLICIT,
            "evidence_excerpt": "Prices sit in the mid range (€€).",
            "notes": None,
        }
    )
    eav[2] = eav[2].model_copy(
        update={
            "value": "coffee beans traceable to a single farm or estate",
            "status": EAVStatus.EXPLICIT,
            "evidence_excerpt": "Single origin coffee is traceable to one farm.",
        }
    )
    eav[3] = eav[3].model_copy(update={"value": None, "status": EAVStatus.MISSING})
    eav.append(
        EAVRow(
            eav_id="eav-6",
            entity_name="Roastery Tours",
            attribute="duration",
            value="90 minutes",
            status=EAVStatus.EXPLICIT,
            evidence_excerpt="Tours last 90 minutes.",
        )
    )
    triples = _triples_a()
    triples[3] = triples[3].model_copy(update={"status": TripleStatus.EXPLICIT})
    del triples[4]  # t5 removed
    triples.append(
        SemanticTriple(
            triple_id="t6",
            subject="Café Noir Roastery",
            predicate="runs",
            object_="roastery tours",
            triple_type=TripleType.CAPABILITY,
            status=TripleStatus.EXPLICIT,
            evidence_excerpt="We run daily roastery tours.",
        )
    )
    coverage = _coverage_a()
    coverage[1] = coverage[1].model_copy(
        update={"status": CoverageStatus.PARTIAL, "coverage_score": 0.5}
    )
    coverage[3] = coverage[3].model_copy(
        update={
            "status": CoverageStatus.MISSING,
            "coverage_score": 0.0,
            "gap_reason": "Comparison removed in revision.",
        }
    )
    claims = _claims_a()
    claims[0] = claims[0].model_copy(
        update={"verification_state": VerificationState.VERIFIED}
    )
    claims[1] = claims[1].model_copy(
        update={"verification_state": VerificationState.UNVERIFIED}
    )
    recs = _recommendations_a()
    recs[0] = recs[0].model_copy(update={"status": RecommendationStatus.DONE})
    recs[3] = recs[3].model_copy(update={"finding_id": "rec-4b"})  # title-match fallback
    del recs[4]  # rec-5 dropped entirely
    recs.append(
        Finding(
            finding_id="rec-6",
            category="eav_gap",
            severity=Severity.MEDIUM,
            title="Add the founding year to the entity box",
            what="The entity box omits the founding year.",
            where=FindingWhere(section_id="entity-box"),
            how=FindingHow(verification_condition="Founding year appears in the box."),
            impact=3,
            confidence_numeric=4,
            effort=1,
            priority_score=12.0,
        )
    )
    scores = {
        "EOS": ComponentScore(score_key="EOS", value=7.5, weight=15, confidence=Confidence.MEDIUM),
        "ERS": ComponentScore(score_key="ERS", value=6.5, weight=15, confidence=Confidence.MEDIUM),
        "KGR": ComponentScore(score_key="KGR", value=6.2, weight=10, confidence=Confidence.LOW),
        "FCS": ComponentScore(
            score_key="FCS", value=6.5, weight=15, confidence=Confidence.MEDIUM,
            observed_queries=3, simulated_queries=5,
        ),
        "PRS": ComponentScore(score_key="PRS", value=7.05, weight=15, confidence=Confidence.HIGH),
        "CWS": ComponentScore(score_key="CWS", value=4.5, weight=20, confidence=Confidence.MEDIUM),
        "HRS": ComponentScore(score_key="HRS", value=7.5, weight=10, confidence=Confidence.HIGH),
        # No TRUST here: baseline-only component must come out as direction "n_a".
    }
    report = AuditReport(
        audit_metadata=_metadata(
            "run-b", created_at="2026-10-16T09:30:00Z", content_hash="sha256:bbbb2222"
        ),
        gate=GateResult(
            status=GateStatus.PASS,
            noncritical_issues=["Optional: add FAQ schema markup"],
        ),
        composite_avr=6.5,
        entities=entities,
        eav_rows=eav,
        triples=triples,
        fanout=_fanout_a(),
        coverage_rows=coverage,
        passage_findings=_passage_findings(),
        claims=claims,
        recommendations=recs,
        swot=SwotAnalysis(
            strengths=["Answer-first intro", "Consistent naming", "Published price tier"],
            weaknesses=["Shipping answer still missing"],
            opportunities=["FAQ block"],
            threats=["Competitor price tables"],
        ),
        measurement_plan=_measurement_plan(),
        sources=_sources(),
    )
    # Assign after construction: a raw dict passed to the union field would be
    # coerced into an (empty) Scorecard; assigning keeps the plain-dict branch.
    report.scores = scores
    return report


def build_report_c() -> AuditReport:
    """Different profile/provider/context packs + extra critical issue."""
    report = build_report_a()
    report.audit_metadata = _metadata(
        "run-c",
        created_at="2026-10-10T09:30:00Z",
        content_hash="sha256:cccc3333",
        score_profile_version="1.1",
        provider_model="openai/gpt-4o-mini",
        context_pack_versions=["brand-pack@2.0"],
    )
    report.gate = GateResult(
        status=GateStatus.FAIL,
        critical_issues=["Fabricated statistic in intro", "Unverifiable safety certification claim"],
        noncritical_issues=["No FAQ section for long-tail questions"],
    )
    # Fan-out/coverage: q8 removed, q9 added.
    report.fanout = [q for q in report.fanout if q.query_id != "q8"] + [
        FanoutQuery(
            query_id="q9",
            query_text="How do I use a moka pot?",
            origin=QueryOrigin.SIMULATED,
            source=QuerySource.GENERATED,
            importance=1,
        )
    ]
    report.coverage_rows = [r for r in report.coverage_rows if r.query_id != "q8"] + [
        CoverageRow(
            query_id="q9",
            query_text="How do I use a moka pot?",
            status=CoverageStatus.MISSING,
            coverage_score=0.0,
            gap_reason="No moka-pot content on the page.",
        )
    ]
    return report
