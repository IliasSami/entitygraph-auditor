"""Workspace read-models: entity registry, content briefs, content analysis.

Everything here is **deterministic and provenance-labelled** — derived from
stored audit reports and context packs, or computed from the submitted text
with pure functions. No model provider is called, so these endpoints work in
zero-API / deterministic-only mode, and nothing is fabricated.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ega_api.errors import ApiError
from ega_api.models import AuditRun, ContextPack, ContextPackVersion, Project
from ega_schemas.workspace import (
    AnalyzeDimension,
    AnalyzeEntityHit,
    AnalyzeHeading,
    AnalyzeMetrics,
    AnalyzeRecommendation,
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeViolation,
    BriefBasis,
    BriefConstraints,
    BriefEntityRef,
    BriefGenerateRequest,
    BriefInformationGain,
    BriefResponse,
    BriefSection,
    BriefSourceItem,
    EntityFact,
    EntitySourceRef,
    WorkspaceEntitiesResponse,
    WorkspaceEntity,
)
from sqlalchemy.orm import Session

ENTITY_DISCLAIMER = (
    "Internal editorial heuristic. Every fact below is derived from stored audit "
    "reports and imported context packs; each row cites its source. No value is "
    "model-generated or inferred."
)
BRIEF_DISCLAIMER = (
    "Deterministic brief assembled from stored audit coverage queries, findings, "
    "claims and context-pack facts. Nothing here is model-generated; each source "
    "cites where it came from. Internal editorial heuristic — verify before publication."
)
ANALYZE_DISCLAIMER = (
    "Deterministic editorial analysis computed locally from the submitted text "
    "(readability, structure, terminology, entity coverage). Internal editorial "
    "heuristic — not a search-engine ranking or an AI-visibility measurement."
)

_WORD_RE = re.compile(r"[A-Za-z0-9'’\-]+")
_SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s|$)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$", re.MULTILINE)
_VOWELS = "aeiouy"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(value)).strip("-") or "entity"


_DISPLAY_KIND = {
    "organization": "Organization",
    "brand": "Organization",
    "competitor": "Organization",
    "product_service": "Service",
    "platform": "Platform",
    "tool": "Platform",
    "person": "Person",
    "location": "Place",
    "concept": "Concept",
    "central": "Concept",
    "problem": "Concept",
    "outcome": "Concept",
    "process": "Concept",
    "use_case": "Concept",
    "audience": "Concept",
    "metric": "Concept",
    "price": "Concept",
    "date": "Concept",
    "standard": "Concept",
    "regulation": "Concept",
    "proof": "Concept",
    "material": "Concept",
    "cta": "Concept",
    "other": "Concept",
}

_SCHEMA_TYPE = {
    "Organization": "schema.org/Organization",
    "Service": "schema.org/Service",
    "Platform": "schema.org/SoftwareApplication",
    "Person": "schema.org/Person",
    "Place": "schema.org/Place",
    "Concept": "schema.org/DefinedTerm",
}


# --------------------------------------------------------------- pack loading


def _normalise_fact(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    entity = row.get("entity") or row.get("entity_name")
    attribute = row.get("attribute") or row.get("key") or row.get("property") or "fact"
    value = row.get("canonical_value") or row.get("value") or row.get("text")
    if value in (None, ""):
        return None
    return {
        "entity": str(entity).strip() if entity else None,
        "attribute": str(attribute).strip(),
        "value": str(value).strip(),
        "source": row.get("verification_source") or row.get("source"),
        "date": row.get("date") or row.get("verified_at"),
    }


def _normalise_banned(row: Any) -> dict | None:
    if isinstance(row, str):
        return {"term": row.strip(), "reason": None, "replacement": None}
    if isinstance(row, dict):
        term = row.get("term") or row.get("text")
        if not term:
            return None
        return {
            "term": str(term).strip(),
            "reason": row.get("reason"),
            "replacement": row.get("suggested_replacement") or row.get("replacement"),
        }
    return None


def _load_packs(session: Session, pack_ids: list[str]) -> list[dict[str, Any]]:
    """Return normalised pack payloads (DB packs first, then built-ins)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pack_id in pack_ids:
        if pack_id in seen:
            continue
        seen.add(pack_id)
        pack = session.get(ContextPack, pack_id)
        if pack is not None:
            latest = (
                session.query(ContextPackVersion)
                .filter(ContextPackVersion.pack_id == pack_id)
                .order_by(ContextPackVersion.id.desc())
                .first()
            )
            payload = latest.payload if latest else {}
            out.append(
                {
                    "pack_id": pack.pack_id,
                    "name": pack.name,
                    "version": pack.version,
                    "canonical_facts": payload.get("canonical_facts") or [],
                    "banned_terms": payload.get("banned_terms") or [],
                    "brand_rules": payload.get("brand_rules") or [],
                }
            )
            continue
        from auditor.context_packs import get_builtin_pack  # noqa: PLC0415

        builtin = get_builtin_pack(pack_id)
        if builtin is not None:
            out.append(
                {
                    "pack_id": builtin.get("pack_id", pack_id),
                    "name": builtin.get("name", "Built-in Pack"),
                    "version": builtin.get("version", "1.0.0"),
                    "canonical_facts": builtin.get("canonical_facts") or [],
                    "banned_terms": builtin.get("banned_terms") or [],
                    "brand_rules": builtin.get("brand_rules") or [],
                }
            )
    return out


# ------------------------------------------------------------ entity registry


def _collect_pack_ids(session: Session, project: Project | None, audits: list[AuditRun]) -> list[str]:
    ids: list[str] = []
    if project is not None and project.context_pack_ids:
        ids.extend(str(x) for x in project.context_pack_ids)
    for audit in audits:
        request = audit.request or {}
        ids.extend(str(x) for x in (request.get("context_pack_ids") or []))
    return ids


def build_entity_registry(session: Session, project_id: str) -> WorkspaceEntitiesResponse:
    project = session.get(Project, project_id)
    if project is None:
        raise ApiError("PROJECT_NOT_FOUND", f"Project {project_id} not found", 404)

    audits = (
        session.query(AuditRun)
        .filter(AuditRun.project_id == project_id, AuditRun.status == "succeeded")
        .order_by(AuditRun.created_at.desc())
        .all()
    )
    packs = _load_packs(session, _collect_pack_ids(session, project, audits))
    base_url = (project.base_url or "").rstrip("/")

    registry: dict[str, dict[str, Any]] = {}

    def _ensure(name: str) -> dict[str, Any]:
        key = _norm(name)
        rec = registry.get(key)
        if rec is None:
            rec = {
                "name": name.strip(),
                "aliases": set(),
                "kinds": [],
                "audits": set(),
                "facts": [],
                "sources": [],
                "origins": set(),
            }
            registry[key] = rec
        return rec

    # 1) Entities + EAV facts from every successful audit report.
    for audit in audits:
        report = audit.report or {}
        short = audit.audit_id[:8]
        for ent in report.get("entities", []):
            name = (ent.get("canonical_name") or "").strip()
            if not name:
                continue
            rec = _ensure(name)
            rec["audits"].add(audit.audit_id)
            rec["kinds"].append(ent.get("kind") or "other")
            for alias in ent.get("aliases") or []:
                if alias:
                    rec["aliases"].add(str(alias))
            rec["origins"].add("audit")
            rec["sources"].append(
                EntitySourceRef(title=f"Audit {short}", url=base_url or None)
            )
        for row in report.get("eav_rows", []):
            name = (row.get("entity_name") or "").strip()
            value = row.get("value")
            if not name or value in (None, ""):
                continue
            rec = _ensure(name)
            rec["audits"].add(audit.audit_id)
            rec["origins"].add("audit")
            rec["facts"].append(
                EntityFact(
                    property=str(row.get("attribute") or "fact"),
                    value=str(value),
                    source=f"Audit {short}",
                    date=(audit.completed_at or audit.created_at).isoformat()
                    if (audit.completed_at or audit.created_at)
                    else None,
                    verified=str(row.get("status") or "").lower() in {"explicit", "verified"},
                )
            )

    # 2) Canonical facts from context packs (grouped by entity where declared).
    for pack in packs:
        for raw in pack["canonical_facts"]:
            fact = _normalise_fact(raw)
            if fact is None:
                continue
            entity_name = fact["entity"]
            if not entity_name:
                # Pack facts without an explicit entity still enrich the central
                # entity if the project declares one.
                entity_name = (project.central_entity or "").strip()
                if not entity_name:
                    continue
            rec = _ensure(entity_name)
            rec["origins"].add("context_pack")
            rec["facts"].append(
                EntityFact(
                    property=fact["attribute"],
                    value=fact["value"],
                    source=fact["source"] or f"Context pack · {pack['name']}",
                    date=fact["date"],
                    verified=True,
                )
            )
            rec["sources"].append(
                EntitySourceRef(title=f"Context pack · {pack['name']} v{pack['version']}")
            )

    entities: list[WorkspaceEntity] = []
    for _key, rec in registry.items():
        # de-duplicate facts and detect attribute conflicts.
        unique_facts: list[EntityFact] = []
        seen_facts: set[tuple[str, str]] = set()
        by_attr: dict[str, set[str]] = {}
        for fact in rec["facts"]:
            sig = (fact.property.lower(), fact.value.lower())
            if sig in seen_facts:
                continue
            seen_facts.add(sig)
            unique_facts.append(fact)
            by_attr.setdefault(fact.property.lower(), set()).add(fact.value)

        conflict_detail: str | None = None
        for attr, values in by_attr.items():
            if len(values) > 1:
                conflict_detail = (
                    f"Conflicting '{attr}' values across sources: "
                    + "; ".join(sorted(values))
                )
                break

        kind_raw = rec["kinds"][0] if rec["kinds"] else "other"
        display_kind = _DISPLAY_KIND.get(str(kind_raw).lower(), "Concept")
        facts_count = len(unique_facts)

        if conflict_detail:
            status = "conflict"
        elif facts_count == 0 and not rec["audits"]:
            status = "needs_review"
        else:
            status = "healthy"

        definition = ""
        for fact in unique_facts:
            if fact.property.lower() in {"definition", "description", "summary"}:
                definition = fact.value
                break
        if not definition:
            parts = []
            if rec["audits"]:
                parts.append(f"appears in {len(rec['audits'])} audited page(s)")
            if facts_count:
                parts.append(f"{facts_count} recorded fact(s)")
            definition = (
                "No canonical definition recorded"
                + ("; " + "; ".join(parts) + "." if parts else ".")
            )

        dates = [f.date for f in unique_facts if f.date]
        last_verified = max(dates) if dates else None
        # de-dup sources
        src_map: dict[str, EntitySourceRef] = {}
        for src in rec["sources"]:
            src_map.setdefault(src.title, src)

        entities.append(
            WorkspaceEntity(
                entity_id=f"ent-{_slug(rec['name'])}",
                canonical_id=f"#{_slug(rec['name'])}",
                name=rec["name"],
                kind=display_kind,
                entity_kind=str(kind_raw),
                aliases=sorted(rec["aliases"]),
                pages_used=len(rec["audits"]),
                facts_count=facts_count,
                last_verified=last_verified,
                status=status,
                conflict_detail=conflict_detail,
                definition=definition,
                at_id=f"{base_url}/{_slug(rec['name'])}" if base_url else f"#{_slug(rec['name'])}",
                schema_type=_SCHEMA_TYPE.get(display_kind, "schema.org/Thing"),
                facts=unique_facts,
                sources=list(src_map.values()),
                origins=sorted(rec["origins"]),
            )
        )

    entities.sort(key=lambda e: (-e.pages_used, -e.facts_count, e.name.lower()))
    return WorkspaceEntitiesResponse(
        project_id=project_id,
        entities=entities,
        generated_at=_iso_now(),
        source_audits=len(audits),
        source_packs=len(packs),
        disclaimer=ENTITY_DISCLAIMER,
    )


# ---------------------------------------------------------------------- briefs


def _resolve_audit(session: Session, project_id: str, audit_id: str | None) -> AuditRun | None:
    if audit_id:
        audit = session.get(AuditRun, audit_id)
        if audit is None or audit.project_id != project_id:
            raise ApiError("AUDIT_NOT_FOUND", f"Audit {audit_id} not found", 404)
        return audit
    return (
        session.query(AuditRun)
        .filter(AuditRun.project_id == project_id, AuditRun.status == "succeeded")
        .order_by(AuditRun.created_at.desc())
        .first()
    )


def _title_case(value: str) -> str:
    value = value.strip().rstrip("?").strip()
    return value[:1].upper() + value[1:] if value else value


def _word_range(index: int) -> str:
    bands = ["120–180 words", "180–240 words", "250–350 words", "200–260 words"]
    return bands[index % len(bands)]


def generate_brief(session: Session, payload: BriefGenerateRequest) -> BriefResponse:
    project = session.get(Project, payload.project_id)
    if project is None:
        raise ApiError("PROJECT_NOT_FOUND", f"Project {payload.project_id} not found", 404)

    audit = _resolve_audit(session, payload.project_id, payload.audit_id)
    report: dict[str, Any] = (audit.report if audit else None) or {}
    metadata = report.get("audit_metadata") or {}

    pack_ids = list(payload.context_pack_ids) or _collect_pack_ids(session, project, [audit] if audit else [])
    packs = _load_packs(session, pack_ids)

    sources: list[BriefSourceItem] = []
    pack_facts: list[str] = []

    # Questions from fan-out / coverage queries.
    fanout = report.get("fanout") or []
    for q in fanout:
        text = (q.get("query_text") or "").strip()
        if not text:
            continue
        importance = int(q.get("importance") or 2)
        tag = "Core intent" if importance >= 3 else "Follow-up"
        sources.append(
            BriefSourceItem(
                id=f"q-{q.get('query_id') or _slug(text)}",
                kind="question",
                title=text,
                source="Coverage query (fan-out)",
                tag=tag,
                provenance=f"audit:{audit.audit_id}" if audit else "audit",
            )
        )

    # Gaps from findings that flag missing coverage.
    for fnd in report.get("findings") or []:
        category = str(fnd.get("category") or "")
        if not any(
            k in category.lower() for k in ("gap", "coverage", "missing", "originality", "entity")
        ):
            continue
        title = (fnd.get("title") or "").strip()
        if not title:
            continue
        sources.append(
            BriefSourceItem(
                id=f"f-{fnd.get('finding_id') or _slug(title)}",
                kind="gap",
                title=title,
                source="Audit finding",
                tag=category or "Gap",
                provenance=f"audit:{audit.audit_id}" if audit else "audit",
            )
        )

    # Facts from claims made in the audited content.
    for claim in report.get("claims") or []:
        statement = (claim.get("statement") or "").strip()
        if not statement:
            continue
        sources.append(
            BriefSourceItem(
                id=f"c-{claim.get('claim_id') or _slug(statement)}",
                kind="fact",
                title=statement,
                source="Audit claim",
                tag=str(claim.get("risk_tier") or "claim"),
                provenance=f"audit:{audit.audit_id}" if audit else "audit",
            )
        )

    # Facts + banned terms from context packs.
    info_gain: list[BriefInformationGain] = []
    for pack in packs:
        for raw in pack["canonical_facts"]:
            fact = _normalise_fact(raw)
            if fact is None:
                continue
            label = f"{fact['attribute']}: {fact['value']}"
            pack_facts.append(label)
            sources.append(
                BriefSourceItem(
                    id=f"p-{_slug(pack['pack_id'])}-{_slug(fact['attribute'])}",
                    kind="fact",
                    title=label,
                    source=f"Context pack · {pack['name']}",
                    tag="Verified fact",
                    provenance=f"pack:{pack['pack_id']}@{pack['version']}",
                )
            )
        for raw in pack["banned_terms"]:
            term = _normalise_banned(raw)
            if term is None:
                continue
            suffix = f" — {term['reason']}" if term.get("reason") else ""
            info_gain.append(
                BriefInformationGain(
                    directive=f"Do NOT use “{term['term']}”{suffix}",
                    polarity="avoid",
                )
            )
        for rule in pack["brand_rules"]:
            statement = ""
            if isinstance(rule, dict):
                statement = rule.get("statement") or ""
            if statement:
                info_gain.append(
                    BriefInformationGain(directive=statement, polarity="do")
                )

    # Sections: prefer coverage queries, else fall back to report entities.
    target_entities = [
        BriefEntityRef(name=e.get("canonical_name", ""), kind=str(e.get("kind") or "concept"))
        for e in (report.get("entities") or [])
        if e.get("canonical_name")
    ]
    central = metadata.get("central_entity") or project.central_entity or project.name
    if not target_entities and central:
        target_entities = [BriefEntityRef(name=str(central), kind="central")]

    sections: list[BriefSection] = []
    query_texts = [s.title for s in sources if s.kind == "question"]
    if query_texts:
        for idx, text in enumerate(query_texts[: payload.max_sections]):
            sections.append(
                BriefSection(
                    id=f"sec-{idx + 1}",
                    h2_number=idx + 1,
                    title=_title_case(text),
                    badge="Answer",
                    entities=target_entities[:2],
                    facts=pack_facts[:2],
                    directive=(
                        f"Answer the query “{text}” directly in the first two sentences, "
                        "then expand with entity-specific evidence. Cite a verified fact "
                        "where one applies."
                    ),
                    word_range=_word_range(idx),
                )
            )
    elif target_entities:
        badges = ["Answer", "Compare", "Explain", "Prove", "Pricing"]
        for idx, ent in enumerate(target_entities[: payload.max_sections]):
            sections.append(
                BriefSection(
                    id=f"sec-{idx + 1}",
                    h2_number=idx + 1,
                    title=f"{ent.name}: what it is and why it matters",
                    badge=badges[idx % len(badges)],
                    entities=[ent],
                    facts=pack_facts[:2],
                    directive=(
                        f"Define {ent.name} for the target audience, state its relevance to "
                        f"{central}, and support the section with a verified fact."
                    ),
                    word_range=_word_range(idx),
                )
            )

    target_query = (
        payload.target_query
        or metadata.get("primary_query")
        or project.central_entity
        or project.name
        or ""
    )
    constraints = BriefConstraints(
        audience=project.audience_icp,
        tone=next(
            (
                r.get("statement")
                for pack in packs
                for r in pack["brand_rules"]
                if isinstance(r, dict) and r.get("statement")
            ),
            None,
        ),
        intent=str(metadata.get("primary_intent") or "") or None,
    )

    return BriefResponse(
        project_id=payload.project_id,
        target_query=target_query,
        sources=sources,
        sections=sections,
        constraints=constraints,
        information_gain=info_gain,
        basis=BriefBasis(
            audit_id=audit.audit_id if audit else None,
            audit_created_at=(audit.created_at.isoformat() if audit and audit.created_at else None),
            context_pack_ids=[p["pack_id"] for p in packs],
            context_pack_versions=[f"{p['pack_id']}@{p['version']}" for p in packs],
        ),
        generated_at=_iso_now(),
        disclaimer=BRIEF_DISCLAIMER,
    )


# ------------------------------------------------------------------- analyzer


def _count_syllables(word: str) -> int:
    word = word.lower()
    if not word:
        return 0
    count = 0
    prev_vowel = False
    for ch in word:
        is_vowel = ch in _VOWELS
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def _band(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 50:
        return "fair"
    return "weak"


def _extract_headings(text: str) -> list[AnalyzeHeading]:
    headings: list[AnalyzeHeading] = []
    for match in _HEADING_RE.finditer(text):
        level = len(match.group(1))
        title = match.group(2).strip()
        is_question = title.endswith("?") or bool(
            re.match(
                r"^(how|what|why|when|where|who|which|can|does|do|is|are|should)\b",
                title,
                re.IGNORECASE,
            )
        )
        headings.append(AnalyzeHeading(level=level, text=title, is_question=is_question))
    return headings


def analyze_content(payload: AnalyzeRequest) -> AnalyzeResponse:
    text = payload.text or ""
    body = _HEADING_RE.sub("", text)
    words = _WORD_RE.findall(body)
    word_count = len(words)
    sentences = [s for s in _SENTENCE_SPLIT.split(body) if s.strip()]
    sentence_count = max(1, len(sentences))
    paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    syllable_total = sum(_count_syllables(w) for w in words) or 1
    words_per_sentence = word_count / sentence_count
    syllables_per_word = syllable_total / max(1, word_count)
    reading_ease = round(206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word, 1)
    fk_grade = round(0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59, 1)
    reading_time = max(1, round(word_count / 220)) if word_count else 0

    headings = _extract_headings(text)
    h1 = [h for h in headings if h.level == 1]
    h2 = [h for h in headings if h.level == 2]
    question_headings = [h for h in headings if h.is_question]

    # Entity coverage.
    lowered = text.lower()
    entity_hits: list[AnalyzeEntityHit] = []
    for name in payload.target_entities:
        clean = (name or "").strip()
        if not clean:
            continue
        count = len(re.findall(re.escape(clean.lower()), lowered))
        status = "missing" if count == 0 else ("thin" if count == 1 else "ok")
        entity_hits.append(AnalyzeEntityHit(name=clean, count=count, expected=True, status=status))

    violations: list[AnalyzeViolation] = []
    for term in payload.banned_terms:
        clean = (term or "").strip()
        if not clean:
            continue
        count = len(re.findall(re.escape(clean.lower()), lowered))
        if count:
            violations.append(AnalyzeViolation(term=clean, count=count))

    # Dimensions (0-100), deterministic.
    length_ratio = word_count / max(1, payload.word_target)
    entities_score = 100
    if entity_hits:
        covered = sum(1 for e in entity_hits if e.status == "ok")
        thin = sum(1 for e in entity_hits if e.status == "thin")
        entities_score = max(0, round(100 * (covered + 0.5 * thin) / len(entity_hits)))
    answer_score = 40
    if sentence_count and words_per_sentence <= 24:
        answer_score += 20
    if question_headings:
        answer_score += 20
    if length_ratio >= 0.6:
        answer_score += 20
    answer_score = min(100, answer_score)
    evidence_score = 100 if not violations else max(15, 100 - 40 * len(violations))
    passages_score = min(100, max(20, round(30 + 40 * min(1.0, len(h2) / 4) + (20 if question_headings else 0))))
    originality_score = min(100, max(30, round(60 + 40 * min(1.0, length_ratio))))

    dimensions = [
        AnalyzeDimension(key="entities", label="Entities", score=entities_score, band=_band(entities_score), note=f"{len(entity_hits)} target entity(ies) tracked"),
        AnalyzeDimension(key="answers", label="Answers", score=answer_score, band=_band(answer_score), note=f"{len(question_headings)} question heading(s)"),
        AnalyzeDimension(key="evidence", label="Evidence", score=evidence_score, band=_band(evidence_score), note=f"{len(violations)} banned-term hit(s)"),
        AnalyzeDimension(key="passages", label="Passages", score=passages_score, band=_band(passages_score), note=f"{len(h2)} H2 section(s)"),
        AnalyzeDimension(key="originality", label="Originality", score=originality_score, band=_band(originality_score), note=f"{word_count} words vs {payload.word_target} target"),
    ]

    recommendations: list[AnalyzeRecommendation] = []
    if h1 and len(h1) > 1:
        recommendations.append(
            AnalyzeRecommendation(
                id="single_h1",
                title="Use exactly one H1 heading",
                detail=f"Found {len(h1)} H1 headings; search engines expect a single page title.",
                dimension="passages",
                impact="medium",
                action="Merge or demote extra H1 headings.",
            )
        )
    if not question_headings:
        recommendations.append(
            AnalyzeRecommendation(
                id="add_question_heading",
                title="Add a question-shaped heading",
                detail="No heading is phrased as a question, so answer-engine extraction is weaker.",
                dimension="answers",
                impact="high",
                action="Rewrite one H2 as a real question the audience asks.",
            )
        )
    if words_per_sentence > 24:
        recommendations.append(
            AnalyzeRecommendation(
                id="shorten_sentences",
                title="Shorten sentences",
                detail=f"Average sentence length is {words_per_sentence:.1f} words; aim for under 24.",
                dimension="answers",
                impact="medium",
                action="Split long sentences to improve answer conciseness.",
            )
        )
    missing = [e.name for e in entity_hits if e.status == "missing"]
    thin = [e.name for e in entity_hits if e.status == "thin"]
    if missing:
        recommendations.append(
            AnalyzeRecommendation(
                id="add_missing_entities",
                title="Cover missing target entities",
                detail="Not mentioned: " + ", ".join(missing),
                dimension="entities",
                impact="high",
                action="Introduce and define the missing entities.",
            )
        )
    if thin:
        recommendations.append(
            AnalyzeRecommendation(
                id="reinforce_entities",
                title="Reinforce thin entities",
                detail="Mentioned only once: " + ", ".join(thin),
                dimension="entities",
                impact="medium",
                action="Add a second, contextual mention for each thin entity.",
            )
        )
    for violation in violations:
        recommendations.append(
            AnalyzeRecommendation(
                id=f"banned_{_slug(violation.term)}",
                title=f"Remove banned term “{violation.term}”",
                detail=f"Appears {violation.count}x; a context pack bans this term.",
                dimension="evidence",
                impact="high",
                action="Replace with an objective, verifiable statement.",
            )
        )
    if length_ratio < 0.6:
        recommendations.append(
            AnalyzeRecommendation(
                id="expand_length",
                title="Expand coverage",
                detail=f"{word_count} words vs a {payload.word_target}-word target.",
                dimension="originality",
                impact="low",
                action="Add the sub-topics identified in the coverage gaps.",
            )
        )

    overall = round(sum(d.score for d in dimensions) / len(dimensions)) if dimensions else 0
    return AnalyzeResponse(
        metrics=AnalyzeMetrics(
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=len(paragraphs),
            reading_time_minutes=reading_time,
            reading_ease=reading_ease,
            flesch_kincaid_grade=fk_grade,
        ),
        headings=headings,
        entities=entity_hits,
        violations=violations,
        dimensions=dimensions,
        recommendations=recommendations,
        overall_score=overall,
        disclaimer=ANALYZE_DISCLAIMER,
    )
