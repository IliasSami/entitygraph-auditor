"""Deterministic page-type, attribute, brand and priority rules (PRD §5, §9.5, §9.6)."""

from auditor.rules.attributes import (
    INTENT_ATTRIBUTES,
    LOCATION_ATTRIBUTES,
    REQUIRED_ATTRIBUTES,
    AttributeSpec,
    attributes_for,
    satisfied_attribute_keys,
)
from auditor.rules.brand_rules import (
    FORBIDDEN_CLAIM_PATTERNS,
    RuleViolation,
    brand_pack_present,
    brand_rule_violations,
    collect_brand_inputs,
    detect_banned_terms,
    detect_canonical_fact_conflicts,
    detect_forbidden_claims,
    normalize_value,
    values_equal,
)
from auditor.rules.page_profiles import (
    PAGE_PROFILES,
    PROFILE_VERSION,
    WEIGHT_PRESETS,
    PageProfile,
    get_profile,
    weight_preset,
)
from auditor.rules.priority import (
    SEVERITY_RANK,
    assign_ranks,
    compute_priority,
    effective_effort,
    is_gate_critical,
    priority_sort,
)

__all__ = [
    "AttributeSpec",
    "FORBIDDEN_CLAIM_PATTERNS",
    "INTENT_ATTRIBUTES",
    "LOCATION_ATTRIBUTES",
    "PAGE_PROFILES",
    "PROFILE_VERSION",
    "PageProfile",
    "REQUIRED_ATTRIBUTES",
    "RuleViolation",
    "SEVERITY_RANK",
    "WEIGHT_PRESETS",
    "assign_ranks",
    "attributes_for",
    "brand_pack_present",
    "brand_rule_violations",
    "collect_brand_inputs",
    "compute_priority",
    "detect_banned_terms",
    "detect_canonical_fact_conflicts",
    "detect_forbidden_claims",
    "effective_effort",
    "get_profile",
    "is_gate_critical",
    "normalize_value",
    "priority_sort",
    "satisfied_attribute_keys",
    "values_equal",
    "weight_preset",
]
