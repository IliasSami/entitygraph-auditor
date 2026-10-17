"""Brand, banned-term, forbidden-claim and canonical-fact rules (PRD §9.5, FR-11).

All evaluators are pure deterministic functions over plain inputs (text plus
structured pack data). They never call an LLM and never mutate their inputs.
The gate in ``ega_scoring.gate`` pulls the inputs from the run state and maps
returned ``RuleViolation`` severities onto gate outcomes:

* ``critical``      → FAIL (not publishable as-is)
* ``high``/``medium``/``low`` → non-critical issues (PASS_WITH_FIXES)
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any, Iterable, Mapping, Optional, Sequence

from ega_schemas.entities import EAVRow
from ega_schemas.enums import EAVStatus, Severity
from ega_schemas.findings import Finding
from ega_schemas.triples import SemanticTriple

_OFFSET_WINDOW = 80


class RuleViolation:
    """Structured result of one deterministic brand-rule evaluation."""

    __slots__ = (
        "rule_id",
        "title",
        "detail",
        "severity",
        "source",
        "start_offset",
        "end_offset",
        "evidence",
    )

    def __init__(
        self,
        rule_id: str,
        title: str,
        detail: str,
        severity: Severity = Severity.HIGH,
        source: str = "",
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None,
        evidence: str = "",
    ) -> None:
        self.rule_id = rule_id
        self.title = title
        self.detail = detail
        self.severity = severity
        self.source = source
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.evidence = evidence

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"RuleViolation({self.rule_id!r}, {self.severity.value!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RuleViolation):
            return NotImplemented
        return (self.rule_id, self.title, self.severity, self.start_offset) == (
            other.rule_id,
            other.title,
            other.severity,
            other.start_offset,
        )

    def __hash__(self) -> int:
        return hash((self.rule_id, self.title, self.start_offset))


# --------------------------------------------------------------------------
# Forbidden absolute / unverifiable claim patterns (PRD §9.5 "prohibited claim")
# --------------------------------------------------------------------------

#: (compiled pattern, rule id, human title, severity)
_FORBIDDEN_CLAIM_PATTERNS: tuple[tuple[str, str, str, Severity], ...] = (
    (r"\bguaranteed\s+(?:to\s+be\s+)?(?:the\s+)?number[\s-]?one\b|\bguaranteed\s+#\s?1\b",
     "forbidden_guaranteed_1", "Guaranteed #1 claim", Severity.CRITICAL),
    (r"(?:^|[\s(\[])#\s?1\b|\bnumber\s+one\b",
     "forbidden_unverifiable_1", "Unverifiable '#1 / number one' superlative", Severity.CRITICAL),
    (r"\b100\s*%\s*(?:effective|effective\b|guaranteed|proven|successful|reliable|accurate|cures?)",
     "forbidden_100pct", "100% effectiveness / guarantee claim", Severity.CRITICAL),
    (r"\b(?:cure[sd]?|curing|heal(?:s|ed)?)\b",
     "forbidden_cure", "Absolute medical cure/heal claim", Severity.CRITICAL),
    (r"\b(?:best|worst|fastest|safest|greatest)\s+(?:in|on)\s+the\s+(?:world|market|industry|planet)\b",
     "forbidden_world_superlative", "Unverifiable world/market superlative", Severity.CRITICAL),
    (r"\bnever\s+(?:fails|disappoints|loses)\b|\balways\s+(?:wins|works|beats)\b",
     "forbidden_absolute", "Absolute outcome guarantee", Severity.CRITICAL),
    (r"\bguaranteed\s+(?:returns?|profits?|results?)\b|\brisk[\s-]?free\s+(?:investment|returns?|profits?)\b",
     "forbidden_guaranteed_return", "Guaranteed financial return claim", Severity.CRITICAL),
    (r"\bmiracle\s+(?:cure|treatment|solution|product)\b",
     "forbidden_miracle", "Miracle-product claim", Severity.CRITICAL),
)

FORBIDDEN_CLAIM_PATTERNS: tuple[tuple[re.Pattern[str], str, str, Severity], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), rule_id, title, severity)
    for pattern, rule_id, title, severity in _FORBIDDEN_CLAIM_PATTERNS
)


def _as_mapping(item: Any) -> Mapping[str, Any]:
    """Normalize dicts and pydantic pack models into a mapping."""
    if isinstance(item, Mapping):
        return item
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "to_dict"):
        return item.to_dict()
    return dict(vars(item))


def _severity_of(raw: Any, default: Severity = Severity.HIGH) -> Severity:
    if raw is None:
        return default
    if isinstance(raw, Severity):
        return raw
    try:
        return Severity(str(raw).lower())
    except ValueError:
        return default


def _find_span(text: str, needle: str) -> tuple[Optional[int], Optional[int], str]:
    """Locate ``needle`` in ``text`` case-insensitively; return offsets + excerpt."""
    if not text or not needle:
        return None, None, ""
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return None, None, ""
    return idx, idx + len(needle), text[idx : idx + len(needle)]


# --------------------------------------------------------------------------
# Banned terms (word-boundary match with allowed-context overrides)
# --------------------------------------------------------------------------


def banned_term_patterns(term_entry: Mapping[str, Any]) -> tuple[re.Pattern[str], list[re.Pattern[str]]]:
    """Compile one banned-term entry into (term pattern, allowed-context patterns)."""
    term = str(term_entry.get("term", "")).strip()
    term_pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE) if term else None
    raw_contexts = term_entry.get("allowed_contexts") or term_entry.get("allow_if") or []
    if isinstance(raw_contexts, str):
        raw_contexts = [raw_contexts]
    allowed = []
    for raw in raw_contexts:
        try:
            allowed.append(re.compile(str(raw), re.IGNORECASE))
        except re.error:
            continue
    return term_pattern, allowed  # type: ignore[return-value]


def detect_banned_terms(text: str, banned_terms: Iterable[Any]) -> list[RuleViolation]:
    """Detect banned brand terms in ``text`` (word-boundary, case-insensitive).

    A term entry may carry ``allowed_contexts`` (regex list): when one of those
    patterns matches the text window around the hit, the hit is allowed and no
    violation is reported. Entry severity defaults to ``high``.
    """
    violations: list[RuleViolation] = []
    if not text:
        return violations
    for entry in banned_terms or []:
        data = _as_mapping(entry)
        term = str(data.get("term", "")).strip()
        if not term:
            continue
        term_pattern, allowed_patterns = banned_term_patterns(data)
        if term_pattern is None:  # pragma: no cover - guarded by term check
            continue
        reason = str(data.get("reason", "Prohibited brand term"))
        severity = _severity_of(data.get("severity"), Severity.HIGH)
        for match in term_pattern.finditer(text):
            window = text[max(0, match.start() - _OFFSET_WINDOW) : match.end() + _OFFSET_WINDOW]
            if any(p.search(window) for p in allowed_patterns):
                continue
            violations.append(
                RuleViolation(
                    rule_id=f"banned_term:{term.lower()}",
                    title=f"Banned term '{term}'",
                    detail=f"Banned term '{term}' used: {reason}",
                    severity=severity,
                    source="banned_term",
                    start_offset=match.start(),
                    end_offset=match.end(),
                    evidence=match.group(0),
                )
            )
    return violations


# --------------------------------------------------------------------------
# Forbidden claim patterns
# --------------------------------------------------------------------------


def detect_forbidden_claims(text: str) -> list[RuleViolation]:
    """Detect absolute/unverifiable claim patterns that block publication (PRD §9.5)."""
    violations: list[RuleViolation] = []
    if not text:
        return violations
    for pattern, rule_id, title, severity in FORBIDDEN_CLAIM_PATTERNS:
        for match in pattern.finditer(text):
            violations.append(
                RuleViolation(
                    rule_id=rule_id,
                    title=title,
                    detail=f"Critical Compliance Trigger: {title} — matched '{match.group(0).strip()}'",
                    severity=severity,
                    source="forbidden_claim",
                    start_offset=match.start(),
                    end_offset=match.end(),
                    evidence=match.group(0).strip(),
                )
            )
    return violations


# --------------------------------------------------------------------------
# Canonical fact conflicts (string equality + fuzzy-normalized comparison)
# --------------------------------------------------------------------------


def normalize_value(value: Any) -> str:
    """Fuzzy normalization for value comparison (case, separators, punctuation)."""
    s = str(value if value is not None else "").casefold().strip()
    s = re.sub(r"(?<=\d),(?=\d{3})", "", s)          # thousands separators
    s = s.replace("%", " pct ").replace("+", " plus ")
    s = re.sub(r"[^a-z0-9.\s]", " ", s)              # drop other punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip(" .")


def values_equal(a: Any, b: Any, fuzzy_threshold: float = 0.92) -> bool:
    """True when two values match by string equality or fuzzy-normalized equality."""
    na, nb = normalize_value(a), normalize_value(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return SequenceMatcher(None, na, nb).ratio() >= fuzzy_threshold


def _fact_parts(fact: Any) -> tuple[str, str, str, str, bool]:
    """Extract (fact_id, entity, attribute, canonical_value, preflagged_conflict)."""
    data = _as_mapping(fact)
    return (
        str(data.get("fact_id") or data.get("id") or "fact"),
        str(data.get("entity", "")).strip(),
        str(data.get("attribute", "")).strip(),
        str(data.get("canonical_value") or data.get("value") or "").strip(),
        bool(data.get("conflict") or data.get("preflagged_conflict")),
    )


def _entity_matches(candidate: str, entity: str) -> bool:
    nc, ne = normalize_value(candidate), normalize_value(entity)
    if not nc or not ne:
        return False
    return nc == ne or ne in nc or nc in ne


def detect_canonical_fact_conflicts(
    canonical_facts: Iterable[Any],
    eav_rows: Sequence[EAVRow] = (),
    claims: Sequence[Any] = (),
    triples: Sequence[SemanticTriple] = (),
    text: str = "",
    findings: Sequence[Finding] = (),
) -> list[RuleViolation]:
    """Detect contradictions between canonical brand facts and audited content.

    Channels checked (PRD §9.5 "material contradictions with a canonical brand
    pack"):

    * EAV rows asserting a different explicit value for the same attribute;
    * semantic triples whose predicate carries the attribute with another object;
    * numeric claims that contradict the canonical value's numbers;
    * findings whose category marks a canonical-fact conflict;
    * pre-flagged pack facts (``conflict: True``) surfaced as non-critical.

    Values are compared by normalized string equality with a fuzzy-equality
    exemption (≥ 0.92 similarity) so trivial spelling variants are not flagged.
    """
    violations: list[RuleViolation] = []
    for fact in canonical_facts or ():
        fact_id, entity, attribute, canonical_value, preflagged = _fact_parts(fact)
        if preflagged:
            violations.append(
                RuleViolation(
                    rule_id=f"pack_conflict:{fact_id}",
                    title="Pack conflict",
                    detail=(
                        f"Pack conflict flagged in context pack for fact '{fact_id}' "
                        f"({entity}.{attribute} = '{canonical_value}') — reconcile the brand pack."
                    ),
                    severity=Severity.MEDIUM,
                    source="pack_conflict",
                )
            )
            continue
        if not attribute or not canonical_value:
            continue
        attr_norm = normalize_value(attribute)

        for row in eav_rows or ():
            if normalize_value(row.attribute) != attr_norm:
                continue
            if not _entity_matches(row.entity_name, entity):
                continue
            if row.status not in (EAVStatus.EXPLICIT, EAVStatus.CONFLICTING, EAVStatus.UNVERIFIED):
                continue
            if not row.value or values_equal(row.value, canonical_value):
                continue
            start, end, excerpt = _find_span(text, str(row.value))
            violations.append(
                RuleViolation(
                    rule_id=f"canonical_conflict:{fact_id}:{row.eav_id}",
                    title="Canonical fact contradiction",
                    detail=(
                        f"Content asserts {entity}.{attribute} = '{row.value}' "
                        f"but the canonical brand pack states '{canonical_value}' "
                        f"(row {row.eav_id}, status={row.status.value})."
                    ),
                    severity=Severity.CRITICAL,
                    source="canonical_fact",
                    start_offset=start,
                    end_offset=end,
                    evidence=excerpt or str(row.value),
                )
            )

        for triple in triples or ():
            if not _entity_matches(triple.subject, entity):
                continue
            pred_norm = normalize_value(triple.predicate)
            if attr_norm not in pred_norm and not any(
                word and word in pred_norm for word in attr_norm.split()
            ):
                continue
            if values_equal(triple.object_, canonical_value):
                continue
            start, end, excerpt = _find_span(text, triple.object_)
            violations.append(
                RuleViolation(
                    rule_id=f"canonical_conflict:{fact_id}:{triple.triple_id}",
                    title="Canonical fact contradiction",
                    detail=(
                        f"Triple '{triple.subject} {triple.predicate} {triple.object_}' "
                        f"contradicts canonical value '{canonical_value}' for "
                        f"{entity}.{attribute} (triple {triple.triple_id})."
                    ),
                    severity=Severity.CRITICAL,
                    source="canonical_fact",
                    start_offset=start,
                    end_offset=end,
                    evidence=excerpt or triple.object_,
                )
            )

        canon_numbers = set(re.findall(r"\d+(?:\.\d+)?", canonical_value))
        attr_words = [w for w in attr_norm.split() if w]
        for claim in claims or ():
            data = _as_mapping(claim)
            statement = str(data.get("statement", ""))
            st_norm = normalize_value(statement)
            mentions_attr = any(w in st_norm for w in attr_words) if attr_words else False
            claim_numbers = set(re.findall(r"\d+(?:\.\d+)?", statement))
            numeric_contradiction = bool(canon_numbers and claim_numbers and (claim_numbers & canon_numbers) == set())
            fuzzy_value_present = normalize_value(canonical_value) and normalize_value(canonical_value) in st_norm
            if mentions_attr and numeric_contradiction and not fuzzy_value_present:
                claim_id = str(data.get("claim_id", "claim"))
                start, end, excerpt = _find_span(text, statement[:60])
                violations.append(
                    RuleViolation(
                        rule_id=f"canonical_conflict:{fact_id}:{claim_id}",
                        title="Canonical fact contradiction",
                        detail=(
                            f"Claim '{statement}' carries numbers that contradict the canonical "
                            f"{entity}.{attribute} = '{canonical_value}' (claim {claim_id})."
                        ),
                        severity=Severity.CRITICAL,
                        source="canonical_fact",
                        start_offset=start,
                        end_offset=end,
                        evidence=excerpt or statement[:80],
                    )
                )

    # Findings raised by agents that already mark canonical-fact conflicts.
    for finding in findings or ():
        category = (finding.category or "").lower()
        if "canonical" in category and "conflict" in category:
            violations.append(
                RuleViolation(
                    rule_id=f"finding_conflict:{finding.finding_id}",
                    title="Canonical fact contradiction",
                    detail=f"Agent finding '{finding.title}' reports a canonical fact conflict.",
                    severity=Severity.CRITICAL,
                    source="finding",
                )
            )
    return violations


# --------------------------------------------------------------------------
# Pack helpers
# --------------------------------------------------------------------------


def collect_brand_inputs(
    brand_rules: Sequence[Any] = (),
    banned_terms: Sequence[Any] = (),
    canonical_facts: Sequence[Any] = (),
    context_packs: Sequence[Any] = (),
) -> tuple[list[Any], list[Any], list[Any]]:
    """Flatten brand rules, banned terms and canonical facts from state/packs.

    Explicit lists win; ``context_packs`` (dicts or ``ContextPack`` models) are
    scanned for the same keys as a fallback.
    """
    rules: list[Any] = list(brand_rules or [])
    terms: list[Any] = list(banned_terms or [])
    facts: list[Any] = list(canonical_facts or [])
    for pack in context_packs or ():
        data = _as_mapping(pack)
        rules.extend(data.get("brand_rules") or [])
        terms.extend(data.get("banned_terms") or [])
        facts.extend(data.get("canonical_facts") or [])
    return rules, terms, facts


def brand_pack_present(
    brand_rules: Sequence[Any] = (),
    banned_terms: Sequence[Any] = (),
    canonical_facts: Sequence[Any] = (),
) -> bool:
    """True when at least one brand-pack rule/term/fact is configured (PRD §9.5)."""
    return bool(brand_rules or banned_terms or canonical_facts)


def brand_rule_violations(text: str, brand_rules: Sequence[Any]) -> list[RuleViolation]:
    """Evaluate brand rules that are machine-checkable.

    A brand rule dict can carry either a ``pattern`` (regex to enforce on the
    text) or a pre-flagged ``violated: True`` marker produced upstream. Rules
    without either marker are configuration only and are not evaluated
    deterministically.
    """
    violations: list[RuleViolation] = []
    if not text:
        return violations
    for entry in brand_rules or ():
        data = _as_mapping(entry)
        if data.get("conflict"):
            # Handled by canonical-fact conflict reporting as a pack conflict.
            continue
        rule_id = str(data.get("rule_id") or data.get("id") or "brand_rule")
        severity = _severity_of(data.get("severity"), Severity.HIGH)
        statement = str(data.get("statement", "")).strip()
        pattern_raw = data.get("pattern")
        if pattern_raw:
            try:
                pattern = re.compile(str(pattern_raw), re.IGNORECASE)
            except re.error:
                continue
            for match in pattern.finditer(text):
                violations.append(
                    RuleViolation(
                        rule_id=f"brand_rule:{rule_id}",
                        title=f"Brand rule {rule_id} violated",
                        detail=(
                            f"Brand rule '{rule_id}' forbids content matching "
                            f"'{pattern_raw}': matched '{match.group(0).strip()}'."
                        ),
                        severity=severity,
                        source="brand_rule",
                        start_offset=match.start(),
                        end_offset=match.end(),
                        evidence=match.group(0).strip(),
                    )
                )
        elif bool(data.get("violated")):
            violations.append(
                RuleViolation(
                    rule_id=f"brand_rule:{rule_id}",
                    title=f"Brand rule {rule_id} violated",
                    detail=f"Brand rule '{rule_id}' violated: {statement or 'no detail supplied'}",
                    severity=severity,
                    source="brand_rule",
                )
            )
    return violations
