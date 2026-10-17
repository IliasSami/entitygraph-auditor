"""Shared enum vocabulary for EntityGraph Auditor.

Every enum here is part of the public contract: it is exported to JSON Schema
for the MCP server and consumed by the frontend. Values are lowercase strings
so that JSON serialization is stable and language-neutral.
"""

from __future__ import annotations

from enum import Enum


class PageType(str, Enum):
    """Required page-type system (PRD §5). User selection always overrides the classifier."""

    HOMEPAGE = "homepage"
    ABOUT = "about"
    SERVICE = "service"
    LOCAL_SERVICE = "local_service"
    ARTICLE = "article"
    GLOSSARY = "glossary"
    LISTICLE = "listicle"
    COMPARISON = "comparison"
    CASE_STUDY = "case_study"
    SAAS_B2B = "saas_b2b"
    INTEGRATION = "integration"
    PAID_LANDING = "paid_landing"
    PRODUCT_CATEGORY = "product_category"
    TRUST_POLICY = "trust_policy"
    DOCS = "docs"
    GENERAL = "general"


class IntentClass(str, Enum):
    INFORMATIONAL = "informational"
    COMMERCIAL = "commercial"
    TRANSACTIONAL = "transactional"
    NAVIGATIONAL = "navigational"
    LOCAL = "local"
    COMPARISON = "comparison"
    EVALUATION = "evaluation"
    RESEARCH = "research"


class AnswerShape(str, Enum):
    DEFINITION = "definition"
    CHECKLIST = "checklist"
    PROCEDURE = "procedure"
    SHORTLIST = "shortlist"
    TABLE = "table"
    COMPARISON_VERDICT = "comparison_verdict"
    PRICING_FACT = "pricing_fact"
    RISK_EXPLANATION = "risk_explanation"
    PROOF_BLOCK = "proof_block"
    CTA = "cta"


class EntityKind(str, Enum):
    CENTRAL = "central"
    BRAND = "brand"
    ORGANIZATION = "organization"
    PRODUCT_SERVICE = "product_service"
    PERSON = "person"
    LOCATION = "location"
    CONCEPT = "concept"
    PROBLEM = "problem"
    OUTCOME = "outcome"
    PROCESS = "process"
    TOOL = "tool"
    MATERIAL = "material"
    AUDIENCE = "audience"
    USE_CASE = "use_case"
    PLATFORM = "platform"
    COMPETITOR = "competitor"
    METRIC = "metric"
    PRICE = "price"
    DATE = "date"
    STANDARD = "standard"
    REGULATION = "regulation"
    PROOF = "proof"
    CTA = "cta"
    OTHER = "other"


class ExtractionMethod(str, Enum):
    DETERMINISTIC = "deterministic"
    DICTIONARY = "dictionary"
    NER_LOCAL = "ner_local"
    LLM = "llm"
    MERGED = "merged"


class EAVStatus(str, Enum):
    EXPLICIT = "explicit"
    VAGUE = "vague"
    MISSING = "missing"
    CONFLICTING = "conflicting"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"


class TripleStatus(str, Enum):
    EXPLICIT = "explicit"
    IMPLIED = "implied"
    MISSING = "missing"
    WRONG = "wrong"
    UNSUPPORTED = "unsupported"


class TripleType(str, Enum):
    CATEGORY = "category"
    CAPABILITY = "capability"
    AUDIENCE = "audience"
    GEOGRAPHY = "geography"
    PROCESS = "process"
    OUTCOME = "outcome"
    PRICE = "price"
    INTEGRATION = "integration"
    AUTHORITY = "authority"
    COMPARISON = "comparison"
    REQUIREMENT = "requirement"
    SAFETY_COMPLIANCE = "safety_compliance"
    CAUSE_EFFECT = "cause_effect"
    OTHER = "other"


class EvidenceLabel(str, Enum):
    OFFICIAL = "official"
    MEASURED_STUDY = "measured_study"
    FIRST_PARTY = "first_party"
    PRACTITIONER = "practitioner"
    ANALYTICAL_INFERENCE = "analytical_inference"
    SPECULATIVE = "speculative"
    UNVERIFIED = "unverified"


class ClaimRiskTier(str, Enum):
    ORDINARY = "ordinary"
    HIGH_STAKES = "high_stakes"
    REGULATED = "regulated"


class VerificationState(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"
    NOT_ASSESSED = "not_assessed"


class GateStatus(str, Enum):
    PASS = "pass"
    PASS_WITH_FIXES = "pass_with_fixes"
    FAIL = "fail"
    NOT_CONFIGURED = "not_configured"
    NOT_ASSESSED = "not_assessed"


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NOT_ASSESSED = "not_assessed"


class QueryOrigin(str, Enum):
    OBSERVED = "observed"
    SIMULATED = "simulated"


class QuerySource(str, Enum):
    GSC = "gsc"
    BING = "bing"
    SERP_PAA = "serp_paa"
    USER_BRIEF = "user_brief"
    COMPETITOR = "competitor"
    TOPICAL_MAP = "topical_map"
    GENERATED = "generated_hypothesis"
    OTHER = "other"


class QueryScope(str, Enum):
    THIS_PAGE = "this_page"
    SIBLING = "sibling_page"
    OUT_OF_SCOPE = "out_of_scope"


class CoverageStatus(str, Enum):
    COVERED = "covered"
    PARTIAL = "partial"
    MISSING = "missing"
    EXCLUDED = "excluded"  # belongs elsewhere / out of scope → removed from denominator


class RecommendationStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DISMISSED = "dismissed"


class ResultOrigin(str, Enum):
    """How a stage result was produced (shown in the run timeline)."""

    DETERMINISTIC = "deterministic"
    MODEL = "model_generated"
    EXTERNAL = "externally_verified"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CACHED = "cached"


class AuditDepth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class SourceProfile(str, Enum):
    OFFLINE = "offline"
    LOCAL_WEB = "local_web_search"
    USER_SOURCES = "user_supplied_sources"
    CONNECTED = "connected_data"


class SensitivityTier(str, Enum):
    ORDINARY = "ordinary"
    HIGH_STAKES = "high_stakes"
    REGULATED = "regulated"


class ScoreKey(str, Enum):
    EOS = "EOS"
    ERS = "ERS"
    KGR = "KGR"
    FCS = "FCS"
    PRS = "PRS"
    CWS = "CWS"
    HRS = "HRS"
    AVR = "AVR"
    # optional components
    INTENT = "INTENT"
    LOCAL_FIT = "LOCAL_FIT"
    PAID_FIT = "PAID_FIT"
    CONVERSION = "CONVERSION"
    TRUST = "TRUST"
    LINKS = "LINKS"


CORE_SCORE_KEYS: tuple[ScoreKey, ...] = (
    ScoreKey.EOS,
    ScoreKey.ERS,
    ScoreKey.KGR,
    ScoreKey.FCS,
    ScoreKey.PRS,
    ScoreKey.CWS,
    ScoreKey.HRS,
)
